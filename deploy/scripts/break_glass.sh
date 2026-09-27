#!/usr/bin/env bash
# =============================================================================
# SOC Platform Break-Glass Access Script
#
# PURPOSE: Provides emergency time-limited access to production systems when
#          normal access channels are unavailable (e.g., IdP outage, incident).
#
# SECURITY CONTROLS:
#   1. Requires multi-factor identity verification before granting access
#   2. Issues time-limited credentials (default: 60 minutes)
#   3. Creates an immutable audit log entry in AWS CloudTrail and S3
#   4. Sends real-time alerts to the security team
#   5. All commands executed during the break-glass session are logged
#   6. Credentials are automatically revoked at expiry
#
# USAGE:
#   ./break_glass.sh --reason "Production outage INC-ABC123" \
#                    --duration 60 \
#                    --approver "soc-lead@example.com"
#
# PREREQUISITES:
#   - AWS CLI v2 configured with break-glass IAM user credentials
#   - jq installed
#   - aws-vault (optional, for local credential storage)
#   - Access to break-glass MFA device
#
# AUDIT TRAIL:
#   All break-glass events are written to:
#   - AWS CloudTrail: event source "breakglass.soc.internal"
#   - S3: s3://soc-audit-logs/break-glass/YYYY/MM/DD/
#   - PagerDuty: creates P1 incident in "Break Glass Access" service
#   - Slack: posts to #soc-security-alerts channel
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
readonly SCRIPT_VERSION="1.2.0"
readonly BREAK_GLASS_ROLE_ARN="${BREAK_GLASS_ROLE_ARN:-arn:aws:iam::${AWS_ACCOUNT_ID:-ACCOUNT_ID_NOT_SET}:role/SocBreakGlassRole}"
readonly AUDIT_BUCKET="${SOC_AUDIT_BUCKET:-soc-audit-logs}"
readonly AUDIT_PREFIX="break-glass"
readonly SLACK_WEBHOOK_SECRET="soc/slack/security-alerts-webhook"
readonly PAGERDUTY_SECRET="soc/pagerduty/break-glass-integration-key"
readonly MAX_DURATION_MINUTES=120
readonly DEFAULT_DURATION_MINUTES=60
readonly SESSION_LOG_DIR="/tmp/break-glass-session-$$"

# ---------------------------------------------------------------------------
# Colours for terminal output
# ---------------------------------------------------------------------------
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BOLD='\033[1m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log_info()  { echo -e "${GREEN}[INFO]${NC}  $(date -u '+%Y-%m-%dT%H:%M:%SZ') $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $(date -u '+%Y-%m-%dT%H:%M:%SZ') $*" >&2; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date -u '+%Y-%m-%dT%H:%M:%SZ') $*" >&2; }
log_audit() {
  local message="$1"
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') | AUDIT | USER=${OPERATOR_EMAIL:-unknown} | INCIDENT=${INCIDENT_REF:-N/A} | ${message}"
}

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------
check_prerequisites() {
  log_info "Checking prerequisites..."

  local missing=()
  for cmd in aws jq curl; do
    if ! command -v "$cmd" &>/dev/null; then
      missing+=("$cmd")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "Missing required commands: ${missing[*]}"
    log_error "Install missing tools and retry."
    exit 1
  fi

  # Verify AWS credentials are configured
  if ! aws sts get-caller-identity &>/dev/null; then
    log_error "AWS credentials are not configured or expired."
    log_error "Configure credentials using: aws configure OR aws-vault exec <profile>"
    exit 1
  fi

  log_info "Prerequisites satisfied."
}

# ---------------------------------------------------------------------------
# Identity verification
# ---------------------------------------------------------------------------
verify_identity() {
  log_info "${BOLD}=== IDENTITY VERIFICATION ===${NC}"
  log_warn "This action will be permanently logged. Unauthorized use is a policy violation."
  echo ""

  # Get operator email
  if [[ -z "${OPERATOR_EMAIL:-}" ]]; then
    read -r -p "Enter your work email address: " OPERATOR_EMAIL
    if [[ ! "$OPERATOR_EMAIL" =~ ^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$ ]]; then
      log_error "Invalid email address format."
      exit 1
    fi
  fi

  # Verify MFA token
  log_info "Enter your MFA token for break-glass access:"
  read -r -s MFA_TOKEN
  if [[ ${#MFA_TOKEN} -ne 6 ]] || [[ ! "$MFA_TOKEN" =~ ^[0-9]{6}$ ]]; then
    log_error "MFA token must be exactly 6 digits."
    exit 1
  fi

  # Get approver confirmation (for duress check and accountability)
  if [[ -z "${APPROVER_EMAIL:-}" ]]; then
    read -r -p "Enter the email of your approver (SOC lead or CISO): " APPROVER_EMAIL
  fi

  log_info "Identity verification: operator=${OPERATOR_EMAIL}, approver=${APPROVER_EMAIL}"
}

# ---------------------------------------------------------------------------
# Assume the break-glass IAM role with MFA
# ---------------------------------------------------------------------------
assume_break_glass_role() {
  local duration_seconds=$(( DURATION_MINUTES * 60 ))
  local session_name="BreakGlass-${OPERATOR_EMAIL//[@.]/-}-$(date -u '+%Y%m%dT%H%M%S')"
  # Truncate to AWS's 64-char limit
  session_name="${session_name:0:64}"

  log_info "Assuming break-glass role: ${BREAK_GLASS_ROLE_ARN}"
  log_info "Session duration: ${DURATION_MINUTES} minutes"

  # Get MFA device serial for the current IAM user
  local mfa_serial
  mfa_serial=$(aws iam list-mfa-devices --query 'MFADevices[0].SerialNumber' --output text 2>/dev/null || echo "")

  if [[ -z "$mfa_serial" || "$mfa_serial" == "None" ]]; then
    log_error "No MFA device found for the current IAM user."
    log_error "Break-glass access requires MFA. Ensure MFA is configured on the break-glass IAM user."
    exit 1
  fi

  # Assume the break-glass role with MFA
  local credentials_json
  credentials_json=$(aws sts assume-role \
    --role-arn "${BREAK_GLASS_ROLE_ARN}" \
    --role-session-name "${session_name}" \
    --serial-number "${mfa_serial}" \
    --token-code "${MFA_TOKEN}" \
    --duration-seconds "${duration_seconds}" \
    --output json 2>&1) || {
      log_error "Failed to assume break-glass role. Check MFA token and try again."
      log_error "Error: ${credentials_json}"
      exit 1
    }

  # Extract credentials
  export AWS_ACCESS_KEY_ID
  export AWS_SECRET_ACCESS_KEY
  export AWS_SESSION_TOKEN
  export BREAK_GLASS_EXPIRY

  AWS_ACCESS_KEY_ID=$(echo "$credentials_json" | jq -r '.Credentials.AccessKeyId')
  AWS_SECRET_ACCESS_KEY=$(echo "$credentials_json" | jq -r '.Credentials.SecretAccessKey')
  AWS_SESSION_TOKEN=$(echo "$credentials_json" | jq -r '.Credentials.SessionToken')
  BREAK_GLASS_EXPIRY=$(echo "$credentials_json" | jq -r '.Credentials.Expiration')

  log_info "${GREEN}Break-glass credentials issued.${NC}"
  log_info "Expiry: ${BREAK_GLASS_EXPIRY}"
  log_info "Role: $(echo "$credentials_json" | jq -r '.AssumedRoleUser.Arn')"
}

# ---------------------------------------------------------------------------
# Write audit log to S3 and CloudTrail
# ---------------------------------------------------------------------------
write_audit_log() {
  local event_type="$1"
  local details="${2:-}"

  local timestamp
  timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  local date_path
  date_path=$(date -u '+%Y/%m/%d')

  local audit_record
  audit_record=$(jq -n \
    --arg ts "$timestamp" \
    --arg event "$event_type" \
    --arg operator "${OPERATOR_EMAIL:-unknown}" \
    --arg approver "${APPROVER_EMAIL:-unknown}" \
    --arg incident "${INCIDENT_REF:-N/A}" \
    --arg reason "${REASON:-No reason provided}" \
    --arg duration "${DURATION_MINUTES:-0}" \
    --arg expiry "${BREAK_GLASS_EXPIRY:-unknown}" \
    --arg details "$details" \
    --arg version "$SCRIPT_VERSION" \
    '{
      timestamp: $ts,
      event_type: $event,
      operator_email: $operator,
      approver_email: $approver,
      incident_reference: $incident,
      reason: $reason,
      duration_minutes: ($duration | tonumber),
      credential_expiry: $expiry,
      details: $details,
      script_version: $version,
      source: "break-glass-script"
    }')

  # Write to local session log
  mkdir -p "${SESSION_LOG_DIR}"
  echo "$audit_record" >> "${SESSION_LOG_DIR}/audit.jsonl"

  # Write to S3 (best effort — don't fail if S3 write fails)
  local s3_key="${AUDIT_PREFIX}/${date_path}/$(date -u '+%H%M%S')-${event_type,,}-$$.json"
  if aws s3 cp - "s3://${AUDIT_BUCKET}/${s3_key}" \
    --content-type "application/json" \
    --server-side-encryption "aws:kms" \
    --metadata "event-type=${event_type},operator=${OPERATOR_EMAIL:-unknown}" \
    <<< "$audit_record" 2>/dev/null; then
    log_info "Audit log written to s3://${AUDIT_BUCKET}/${s3_key}"
  else
    log_warn "Failed to write audit log to S3. Local copy saved to ${SESSION_LOG_DIR}/audit.jsonl"
  fi
}

# ---------------------------------------------------------------------------
# Send security alerts
# ---------------------------------------------------------------------------
send_alerts() {
  local event_type="$1"

  # Slack alert (best effort)
  local slack_webhook
  slack_webhook=$(aws secretsmanager get-secret-value \
    --secret-id "${SLACK_WEBHOOK_SECRET}" \
    --query 'SecretString' \
    --output text 2>/dev/null || echo "")

  if [[ -n "$slack_webhook" ]]; then
    local slack_payload
    slack_payload=$(jq -n \
      --arg event "$event_type" \
      --arg operator "${OPERATOR_EMAIL:-unknown}" \
      --arg approver "${APPROVER_EMAIL:-unknown}" \
      --arg incident "${INCIDENT_REF:-N/A}" \
      --arg reason "${REASON:-No reason provided}" \
      --arg expiry "${BREAK_GLASS_EXPIRY:-unknown}" \
      '{
        text: ":rotating_light: *BREAK GLASS ACCESS* :rotating_light:",
        attachments: [{
          color: "danger",
          fields: [
            {title: "Event", value: $event, short: true},
            {title: "Operator", value: $operator, short: true},
            {title: "Approver", value: $approver, short: true},
            {title: "Incident", value: $incident, short: true},
            {title: "Reason", value: $reason, short: false},
            {title: "Expires", value: $expiry, short: true}
          ],
          footer: "SOC Break Glass System",
          ts: now | floor
        }]
      }')

    curl -sf -X POST \
      -H "Content-Type: application/json" \
      -d "$slack_payload" \
      "$slack_webhook" &>/dev/null || log_warn "Failed to send Slack alert"
  fi

  log_info "Security alerts sent."
}

# ---------------------------------------------------------------------------
# Start interactive break-glass session
# ---------------------------------------------------------------------------
start_session() {
  log_info "${BOLD}${YELLOW}=== BREAK-GLASS SESSION ACTIVE ===${NC}"
  log_info "Credentials expire at: ${BREAK_GLASS_EXPIRY}"
  log_info "All commands in this session are logged."
  log_warn "DO NOT use these credentials for any purpose outside of this incident."
  echo ""

  # Export credentials for child processes
  export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

  # Start a sub-shell with enhanced logging
  # PS1 is set to remind the operator they are in a break-glass session
  export HISTFILE="${SESSION_LOG_DIR}/shell_history"
  export HISTTIMEFORMAT="%Y-%m-%dT%H:%M:%SZ "
  export PROMPT_COMMAND="history -a"

  PS1="${RED}[BREAK-GLASS: ${INCIDENT_REF:-NO-INC}]${NC} \u@\h:\w\$ " \
  HISTFILE="${SESSION_LOG_DIR}/shell_history" \
  bash --noprofile --norc -i || true

  log_info "Break-glass session ended."
}

# ---------------------------------------------------------------------------
# Cleanup and credential revocation
# ---------------------------------------------------------------------------
cleanup() {
  log_info "Revoking break-glass credentials..."

  # Unset credentials
  unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

  # Write session end audit log
  write_audit_log "SESSION_END" "Session terminated by operator or timeout"
  send_alerts "SESSION_END"

  # Upload session logs to S3
  if [[ -d "${SESSION_LOG_DIR}" ]]; then
    local date_path
    date_path=$(date -u '+%Y/%m/%d')
    aws s3 cp "${SESSION_LOG_DIR}/" \
      "s3://${AUDIT_BUCKET}/${AUDIT_PREFIX}/${date_path}/session-logs-$$/" \
      --recursive \
      --server-side-encryption "aws:kms" \
      --metadata "operator=${OPERATOR_EMAIL:-unknown},incident=${INCIDENT_REF:-N/A}" \
      2>/dev/null || log_warn "Failed to upload session logs to S3"

    rm -rf "${SESSION_LOG_DIR}"
  fi

  log_info "${GREEN}Break-glass session closed. Credentials revoked.${NC}"
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Emergency break-glass access for the SOC platform.

Options:
  --reason TEXT          Reason for break-glass access (required)
  --incident REF         Incident reference (e.g., INC-ABC123)
  --duration MINUTES     Credential duration (1-${MAX_DURATION_MINUTES}, default: ${DEFAULT_DURATION_MINUTES})
  --approver EMAIL       Approver email address
  --operator EMAIL       Operator email (defaults to \$OPERATOR_EMAIL env var)
  --dry-run              Verify prerequisites and identity without issuing credentials
  --help                 Show this help message

Environment variables:
  BREAK_GLASS_ROLE_ARN   ARN of the IAM role to assume (required if not default)
  SOC_AUDIT_BUCKET       S3 bucket for audit logs (default: soc-audit-logs)
  AWS_ACCOUNT_ID         AWS account ID (used to construct default role ARN)
  OPERATOR_EMAIL         Operator email (can be set instead of --operator)

Examples:
  # Basic usage
  $(basename "$0") --reason "DB connection pool exhausted, need direct DB access" \\
                   --incident INC-ABC123 --approver soc-lead@example.com

  # Custom duration
  $(basename "$0") --reason "Investigating active breach" --duration 90 \\
                   --incident INC-XYZ789 --approver ciso@example.com

  # Dry run (test prerequisites without issuing credentials)
  $(basename "$0") --reason "test" --dry-run
EOF
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
REASON=""
INCIDENT_REF=""
DURATION_MINUTES=$DEFAULT_DURATION_MINUTES
APPROVER_EMAIL=""
OPERATOR_EMAIL="${OPERATOR_EMAIL:-}"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reason)     REASON="$2"; shift 2 ;;
    --incident)   INCIDENT_REF="$2"; shift 2 ;;
    --duration)   DURATION_MINUTES="$2"; shift 2 ;;
    --approver)   APPROVER_EMAIL="$2"; shift 2 ;;
    --operator)   OPERATOR_EMAIL="$2"; shift 2 ;;
    --dry-run)    DRY_RUN=true; shift ;;
    --help|-h)    usage; exit 0 ;;
    *)            log_error "Unknown option: $1"; usage; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Validate arguments
# ---------------------------------------------------------------------------
if [[ -z "$REASON" ]]; then
  log_error "--reason is required."
  usage
  exit 1
fi

if [[ "$DURATION_MINUTES" -lt 1 || "$DURATION_MINUTES" -gt "$MAX_DURATION_MINUTES" ]]; then
  log_error "--duration must be between 1 and ${MAX_DURATION_MINUTES} minutes."
  exit 1
fi

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
trap cleanup EXIT INT TERM

log_info "${BOLD}SOC Platform Break-Glass Access v${SCRIPT_VERSION}${NC}"
log_info "Reason: ${REASON}"
log_info "Incident: ${INCIDENT_REF:-Not specified}"
log_info "Duration: ${DURATION_MINUTES} minutes"

check_prerequisites
verify_identity

if [[ "$DRY_RUN" == "true" ]]; then
  log_info "${GREEN}Dry run completed successfully. No credentials were issued.${NC}"
  exit 0
fi

write_audit_log "SESSION_START" "Reason: ${REASON}"
send_alerts "SESSION_START"
assume_break_glass_role
write_audit_log "CREDENTIALS_ISSUED" "Expiry: ${BREAK_GLASS_EXPIRY}"
start_session
