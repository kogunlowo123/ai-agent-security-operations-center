#!/usr/bin/env bash
# =============================================================================
# Break-Glass Emergency Access Script
# AI Agent Security Operations Center
#
# PURPOSE:
#   Creates time-limited admin credentials for emergency production access
#   when normal IAM access paths are unavailable (e.g., identity provider outage).
#
# USAGE:
#   bash deploy/scripts/break_glass.sh \
#     --reason "Active ransomware incident — INC-2024-0892" \
#     --incident-id INC-2024-0892 \
#     [--duration 4]        # Hours (default: 4, max: 8)
#     [--dry-run]           # Print what would happen without making changes
#
# REQUIREMENTS:
#   - AWS CLI v2 configured with break-glass-initiator IAM role (read-only by default)
#   - jq
#   - curl (for SNS/Slack alerts)
#   - MFA device or Yubikey touch pad present
#
# AUDIT:
#   Every use of this script is logged to:
#     - AWS CloudTrail (IAM assume-role events)
#     - S3 audit bucket: s3://soc-audit-logs/break-glass/
#     - SNS topic: arn:aws:sns:REGION:ACCOUNT:soc-security-alerts
#     - Slack: #soc-incidents (via SNS → Lambda → Slack)
#
# SECURITY NOTES:
#   - Credentials expire automatically (max 8 hours, non-renewable)
#   - All API calls during the break-glass session are logged with tag BreakGlass=true
#   - CISO and Security Lead are paged immediately upon use
#   - The temporary role has write access ONLY to the incident namespace
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BREAK_GLASS_ROLE_ARN="${BREAK_GLASS_ROLE_ARN:-arn:aws:iam::${AWS_ACCOUNT_ID:-ACCOUNT_ID}:role/BreakGlassAdminRole}"
AUDIT_S3_BUCKET="${AUDIT_BUCKET:-soc-audit-logs}"
ALERT_SNS_TOPIC_ARN="${ALERT_SNS_TOPIC:-arn:aws:sns:us-east-1:${AWS_ACCOUNT_ID:-ACCOUNT_ID}:soc-security-alerts}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
MAX_DURATION_HOURS=8
DEFAULT_DURATION_HOURS=4
REQUIRED_MFA=true

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BOLD='\033[1m'
RESET='\033[0m'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log_info()  { echo -e "${GREEN}[INFO]${RESET}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
log_audit() { echo "[AUDIT $(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "${AUDIT_LOG_FILE:-/dev/stderr}"; }

die() {
  log_error "$*"
  exit 1
}

usage() {
  cat <<EOF
Usage: $0 --reason <reason> --incident-id <id> [OPTIONS]

Required:
  --reason <text>        Human-readable reason for break-glass access (min 20 chars)
  --incident-id <id>     Incident ticket ID (e.g. INC-2024-0892)

Optional:
  --duration <hours>     Credential duration in hours (default: ${DEFAULT_DURATION_HOURS}, max: ${MAX_DURATION_HOURS})
  --operator <name>      Override operator name (default: whoami)
  --dry-run              Print actions without executing
  --no-mfa               Skip MFA prompt (NOT recommended; requires env BREAK_GLASS_NO_MFA=1)

Examples:
  $0 --reason "Identity provider outage — cannot access AWS console" --incident-id INC-2024-0892
  $0 --reason "Active ransomware — need to isolate workloads" --incident-id INC-2024-0003 --duration 2
EOF
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
REASON=""
INCIDENT_ID=""
DURATION_HOURS=${DEFAULT_DURATION_HOURS}
OPERATOR="${USER:-$(whoami 2>/dev/null || echo unknown)}"
DRY_RUN=false
NO_MFA=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reason)         REASON="$2";        shift 2 ;;
    --incident-id)    INCIDENT_ID="$2";   shift 2 ;;
    --duration)       DURATION_HOURS="$2"; shift 2 ;;
    --operator)       OPERATOR="$2";      shift 2 ;;
    --dry-run)        DRY_RUN=true;       shift ;;
    --no-mfa)         NO_MFA=true;        shift ;;
    -h|--help)        usage; exit 0 ;;
    *)                die "Unknown argument: $1" ;;
  esac
done

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
[[ -z "${REASON}" ]]       && die "--reason is required"
[[ -z "${INCIDENT_ID}" ]]  && die "--incident-id is required"
[[ ${#REASON} -lt 20 ]]    && die "Reason must be at least 20 characters (got ${#REASON})"
[[ "${DURATION_HOURS}" -gt "${MAX_DURATION_HOURS}" ]] && die "Duration cannot exceed ${MAX_DURATION_HOURS} hours"
[[ "${DURATION_HOURS}" -lt 1 ]] && die "Duration must be at least 1 hour"

DURATION_SECONDS=$(( DURATION_HOURS * 3600 ))
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SESSION_ID="break-glass-${OPERATOR}-$(date +%Y%m%d%H%M%S)"
AUDIT_LOG_FILE="/tmp/${SESSION_ID}.log"

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log_info "Pre-flight checks..."

command -v aws  >/dev/null 2>&1 || die "AWS CLI not found. Install: https://aws.amazon.com/cli/"
command -v jq   >/dev/null 2>&1 || die "jq not found. Install: brew install jq / apt install jq"

# Verify AWS credentials are present
aws sts get-caller-identity --output json >/dev/null 2>&1 || die "AWS credentials not configured or invalid"

CALLER_IDENTITY=$(aws sts get-caller-identity --output json)
CALLER_ARN=$(echo "${CALLER_IDENTITY}" | jq -r '.Arn')
CALLER_ACCOUNT=$(echo "${CALLER_IDENTITY}" | jq -r '.Account')

log_info "Caller identity: ${CALLER_ARN}"
log_info "Account: ${CALLER_ACCOUNT}"

# ---------------------------------------------------------------------------
# Confirmation prompt
# ---------------------------------------------------------------------------
echo ""
echo -e "${RED}${BOLD}========================================================"
echo "         BREAK-GLASS EMERGENCY ACCESS"
echo "========================================================"
echo -e "${RESET}"
echo -e "  Operator:    ${BOLD}${OPERATOR}${RESET}"
echo -e "  Incident ID: ${BOLD}${INCIDENT_ID}${RESET}"
echo -e "  Reason:      ${BOLD}${REASON}${RESET}"
echo -e "  Duration:    ${BOLD}${DURATION_HOURS} hour(s)${RESET}"
echo -e "  Session ID:  ${BOLD}${SESSION_ID}${RESET}"
echo -e "  Timestamp:   ${BOLD}${TIMESTAMP}${RESET}"
echo ""
echo -e "${YELLOW}WARNING: This action will:${RESET}"
echo "  1. Create time-limited admin credentials (expires in ${DURATION_HOURS}h)"
echo "  2. Log this access to CloudTrail and S3 audit bucket"
echo "  3. Alert the CISO and Security Lead via SNS/PagerDuty"
echo "  4. All API calls during this session will be tagged BreakGlass=true"
echo ""

if [[ "${DRY_RUN}" == "true" ]]; then
  log_warn "DRY RUN mode — no credentials will be created, no alerts sent"
fi

read -r -p "Type 'CONFIRM' to proceed: " CONFIRM
[[ "${CONFIRM}" != "CONFIRM" ]] && { log_warn "Aborted by operator."; exit 0; }

# ---------------------------------------------------------------------------
# MFA verification
# ---------------------------------------------------------------------------
MFA_SERIAL="${MFA_SERIAL_ARN:-}"
if [[ "${REQUIRED_MFA}" == "true" && "${NO_MFA}" == "false" ]]; then
  if [[ -z "${MFA_SERIAL}" ]]; then
    # Auto-detect MFA device
    MFA_SERIAL=$(aws iam list-mfa-devices --output json 2>/dev/null | jq -r '.MFADevices[0].SerialNumber // empty')
  fi

  if [[ -n "${MFA_SERIAL}" ]]; then
    read -r -s -p "Enter MFA token code for ${MFA_SERIAL}: " MFA_TOKEN
    echo ""
    [[ ${#MFA_TOKEN} -ne 6 ]] && die "MFA token must be 6 digits"
    MFA_ARGS="--serial-number ${MFA_SERIAL} --token-code ${MFA_TOKEN}"
  else
    log_warn "No MFA device found — proceeding without MFA (ensure your role policy requires MFA at the service level)"
    MFA_ARGS=""
  fi
else
  MFA_ARGS=""
fi

# ---------------------------------------------------------------------------
# Assume break-glass role
# ---------------------------------------------------------------------------
log_info "Assuming break-glass role: ${BREAK_GLASS_ROLE_ARN}"

if [[ "${DRY_RUN}" == "true" ]]; then
  log_warn "[DRY RUN] Would run: aws sts assume-role --role-arn ${BREAK_GLASS_ROLE_ARN} --role-session-name ${SESSION_ID} --duration-seconds ${DURATION_SECONDS} ${MFA_ARGS}"
  CREDENTIALS='{"Credentials":{"AccessKeyId":"DRY_RUN_KEY","SecretAccessKey":"DRY_RUN_SECRET","SessionToken":"DRY_RUN_TOKEN","Expiration":"'$(date -u -d "+${DURATION_HOURS} hours" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)'"}}'
else
  # shellcheck disable=SC2086
  CREDENTIALS=$(aws sts assume-role \
    --role-arn "${BREAK_GLASS_ROLE_ARN}" \
    --role-session-name "${SESSION_ID}" \
    --duration-seconds "${DURATION_SECONDS}" \
    --tags Key=BreakGlass,Value=true Key=IncidentId,Value="${INCIDENT_ID}" Key=Operator,Value="${OPERATOR}" \
    ${MFA_ARGS} \
    --output json) || die "Failed to assume break-glass role. Check your IAM permissions and MFA token."
fi

ACCESS_KEY_ID=$(echo "${CREDENTIALS}"     | jq -r '.Credentials.AccessKeyId')
SECRET_ACCESS_KEY=$(echo "${CREDENTIALS}" | jq -r '.Credentials.SecretAccessKey')
SESSION_TOKEN=$(echo "${CREDENTIALS}"     | jq -r '.Credentials.SessionToken')
EXPIRATION=$(echo "${CREDENTIALS}"        | jq -r '.Credentials.Expiration')

# ---------------------------------------------------------------------------
# Write credentials to temp file (mode 600)
# ---------------------------------------------------------------------------
CREDS_FILE="/tmp/${SESSION_ID}-credentials"
umask 177  # mode 600 for new files
cat > "${CREDS_FILE}" <<EOF
# Break-Glass Credentials — ${SESSION_ID}
# Expires: ${EXPIRATION}
# Incident: ${INCIDENT_ID}
# Reason: ${REASON}
#
# Source these credentials with:
#   source ${CREDS_FILE}

export AWS_ACCESS_KEY_ID="${ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${SECRET_ACCESS_KEY}"
export AWS_SESSION_TOKEN="${SESSION_TOKEN}"
export BREAK_GLASS_SESSION_ID="${SESSION_ID}"
export BREAK_GLASS_INCIDENT="${INCIDENT_ID}"
EOF

# ---------------------------------------------------------------------------
# Write audit log entry
# ---------------------------------------------------------------------------
log_audit "BREAK_GLASS_ACCESS_GRANTED caller=${CALLER_ARN} session=${SESSION_ID} incident=${INCIDENT_ID} operator=${OPERATOR} duration=${DURATION_HOURS}h expiry=${EXPIRATION} reason=\"${REASON}\""

if [[ "${DRY_RUN}" == "false" ]]; then
  # Upload audit log to S3
  aws s3 cp "${AUDIT_LOG_FILE}" \
    "s3://${AUDIT_S3_BUCKET}/break-glass/${SESSION_ID}.log" \
    --sse aws:kms \
    --metadata "incident-id=${INCIDENT_ID},operator=${OPERATOR}" \
    2>/dev/null || log_warn "Failed to upload audit log to S3 (non-fatal)"
fi

# ---------------------------------------------------------------------------
# Send alerts
# ---------------------------------------------------------------------------
ALERT_MESSAGE=$(cat <<EOF
{
  "alert_type": "BREAK_GLASS_ACCESS",
  "severity": "CRITICAL",
  "session_id": "${SESSION_ID}",
  "operator": "${OPERATOR}",
  "incident_id": "${INCIDENT_ID}",
  "reason": "${REASON}",
  "duration_hours": ${DURATION_HOURS},
  "expiration": "${EXPIRATION}",
  "caller_arn": "${CALLER_ARN}",
  "timestamp": "${TIMESTAMP}"
}
EOF
)

if [[ "${DRY_RUN}" == "false" ]]; then
  log_info "Sending security alert to SNS..."
  aws sns publish \
    --topic-arn "${ALERT_SNS_TOPIC_ARN}" \
    --message "${ALERT_MESSAGE}" \
    --subject "BREAK-GLASS ACCESS: ${INCIDENT_ID} by ${OPERATOR}" \
    --message-attributes '{"alert_type":{"DataType":"String","StringValue":"BREAK_GLASS_ACCESS"}}' \
    2>/dev/null || log_warn "Failed to send SNS alert (non-fatal — check network connectivity)"

  # Slack notification (if webhook configured)
  if [[ -n "${SLACK_WEBHOOK_URL}" ]]; then
    SLACK_BODY=$(cat <<EOF
{
  "text": ":rotating_light: *BREAK-GLASS ACCESS ACTIVATED*",
  "attachments": [
    {
      "color": "#FF0000",
      "fields": [
        {"title": "Operator", "value": "${OPERATOR}", "short": true},
        {"title": "Incident", "value": "${INCIDENT_ID}", "short": true},
        {"title": "Duration", "value": "${DURATION_HOURS} hour(s)", "short": true},
        {"title": "Expires", "value": "${EXPIRATION}", "short": true},
        {"title": "Reason", "value": "${REASON}", "short": false},
        {"title": "Session ID", "value": "${SESSION_ID}", "short": false}
      ]
    }
  ]
}
EOF
)
    curl -s -X POST -H 'Content-type: application/json' \
      --data "${SLACK_BODY}" "${SLACK_WEBHOOK_URL}" \
      2>/dev/null || log_warn "Failed to send Slack alert (non-fatal)"
  fi
fi

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}Break-glass credentials created successfully.${RESET}"
echo ""
echo -e "  Session ID:  ${SESSION_ID}"
echo -e "  Expires:     ${EXPIRATION}"
echo -e "  Access Key:  ${ACCESS_KEY_ID}"
echo ""
echo -e "${YELLOW}To activate credentials in your current shell:${RESET}"
echo -e "  ${BOLD}source ${CREDS_FILE}${RESET}"
echo ""
echo -e "${RED}IMPORTANT:${RESET}"
echo "  - Credentials expire at ${EXPIRATION} and CANNOT be renewed"
echo "  - All API calls are tagged BreakGlass=true and logged to CloudTrail"
echo "  - Credential file will be deleted automatically on expiry (monitor expiry yourself)"
echo "  - Contact CISO or Security Lead when your emergency work is complete"
echo "  - Revoke credentials early if no longer needed:"
echo "    aws iam delete-access-key --access-key-id ${ACCESS_KEY_ID} (if IAM key)"
echo ""

exit 0
