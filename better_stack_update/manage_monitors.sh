#!/bin/bash

################################################################################
# Better Stack Monitor Management Script
#
# Manages Better Stack monitors with 3 modes:
# 1. Export all monitors to config.json
# 2. Dry-run: Show what would change if config.json is applied
# 3. Apply: Update/Create monitors based on config.json
################################################################################

# Configuration
BASE_URL="https://betteruptime.com/api/v2"
CONFIG_FILE="monitors_config.json"

# Load API token from environment or .env file
if [ -n "$BETTERSTACK_API_TOKEN" ]; then
    API_TOKEN="$BETTERSTACK_API_TOKEN"
elif [ -f ".env" ]; then
    # Source .env file if it exists
    export $(grep -v '^#' .env | xargs)
    API_TOKEN="${BETTERSTACK_API_TOKEN:-}"
else
    API_TOKEN=""
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

################################################################################
# Helper Functions
################################################################################

print_header() {
    printf "\n${BLUE}========================================${NC}\n"
    printf "${BLUE}%s${NC}\n" "$1"
    printf "${BLUE}========================================${NC}\n\n"
}

print_success() {
    printf "${GREEN}✓ %s${NC}\n" "$1"
}

print_error() {
    printf "${RED}✗ %s${NC}\n" "$1"
}

print_warning() {
    printf "${YELLOW}⚠ %s${NC}\n" "$1"
}

print_info() {
    printf "${BLUE}ℹ %s${NC}\n" "$1"
}

################################################################################
# API Functions
################################################################################

fetch_all_monitors() {
    local page=1
    local temp_file="/tmp/betterstack_monitors_$$.json"
    local output_file="/tmp/betterstack_all_$$.json"

    # Initialize with empty array
    echo "[]" > "$output_file"

    printf "${BLUE}ℹ Fetching monitors from Better Stack API...${NC}\n" >&2

    while true; do
        response=$(curl -s -H "Authorization: Bearer $API_TOKEN" \
            "$BASE_URL/monitors?page=$page&per_page=100")

        # Extract monitors from current page
        monitors=$(echo "$response" | jq -c '.data' 2>/dev/null)

        # Check if we got any monitors
        if [ "$monitors" == "[]" ] || [ "$monitors" == "null" ] || [ -z "$monitors" ]; then
            break
        fi

        # Append to output file
        jq -c ". + $monitors" "$output_file" > "$temp_file" && mv "$temp_file" "$output_file"

        count=$(echo "$monitors" | jq 'length')
        printf "${BLUE}ℹ   Page %d: Fetched %d monitors${NC}\n" "$page" "$count" >&2

        # Check if there's a next page
        next=$(echo "$response" | jq -r '.pagination.next' 2>/dev/null)
        if [ "$next" == "null" ] || [ -z "$next" ]; then
            break
        fi

        page=$((page + 1))
    done

    total=$(jq 'length' "$output_file")
    printf "${GREEN}✓ Total monitors fetched: %s${NC}\n" "$total" >&2

    # Output to stdout
    cat "$output_file"

    # Cleanup
    rm -f "$temp_file" "$output_file"
}

################################################################################
# Option 1: Export all monitors to config.json
################################################################################

export_monitors() {
    print_header "OPTION 1: Export Monitors to Config"

    # Fetch all monitors and save to temp file
    local temp_monitors="/tmp/betterstack_export_$$.json"
    fetch_all_monitors > "$temp_monitors"

    # Check if fetch was successful
    if [ ! -s "$temp_monitors" ]; then
        print_error "No monitors fetched. Please check your API token and connection."
        rm -f "$temp_monitors"
        return 1
    fi

    # Transform monitors to simplified config format
    print_info "Transforming monitors to config format..."

    jq '{
        monitors: [
            .[] | {
                id: .id,
                url: .attributes.url,
                name: .attributes.pronounceable_name,
                monitor_type: .attributes.monitor_type,
                monitor_group_id: .attributes.monitor_group_id,
                team_name: .attributes.team_name,
                check_frequency: .attributes.check_frequency,
                request_timeout: .attributes.request_timeout,
                recovery_period: .attributes.recovery_period,
                confirmation_period: .attributes.confirmation_period,
                http_method: .attributes.http_method,
                verify_ssl: .attributes.verify_ssl,
                follow_redirects: .attributes.follow_redirects,
                remember_cookies: .attributes.remember_cookies,
                call: .attributes.call,
                sms: .attributes.sms,
                email: .attributes.email,
                push: .attributes.push,
                critical_alert: .attributes.critical_alert,
                paused: .attributes.paused,
                regions: .attributes.regions,
                expected_status_codes: .attributes.expected_status_codes,
                request_headers: .attributes.request_headers,
                request_body: .attributes.request_body,
                required_keyword: .attributes.required_keyword,
                port: .attributes.port
            }
        ]
    }' "$temp_monitors" > "$CONFIG_FILE"

    monitor_count=$(jq '.monitors | length' "$CONFIG_FILE")
    print_success "Exported $monitor_count monitors to $CONFIG_FILE"

    # Show summary by group/type
    print_header "Summary by Monitor Type"
    jq -r '.monitors | group_by(.monitor_type) | map({type: .[0].monitor_type, count: length}) | .[] |
        "\(.count) monitors of type: \(.type)"' "$CONFIG_FILE"

    print_header "Summary by Domain"
    jq -r '.monitors | [.[].url |
        if contains("://") then split("://")[1] | split("/")[0]
        else split("/")[0] end] |
        group_by(.) | map({domain: .[0], count: length}) | .[] |
        "\(.count) monitors on: \(.domain)"' "$CONFIG_FILE"

    # Cleanup
    rm -f "$temp_monitors"
}

################################################################################
# Option 2: Dry-run (show what would change)
################################################################################

compare_monitors() {
    local config_file="$1"
    local current_file="$2"
    local changes_file="/tmp/betterstack_changes_$$.json"

    # Create a comparison report
    jq -n --slurpfile config "$config_file" --slurpfile current "$current_file" '
    # Index current monitors by ID for quick lookup
    ($current[0].monitors | map({(.id): .}) | add // {}) as $current_by_id |

    # Process each monitor from config
    ($config[0].monitors | map(
        . as $cfg_monitor |
        if $cfg_monitor.id == null or $cfg_monitor.id == "" then
            # No ID means new monitor to create
            {action: "create", monitor: $cfg_monitor}
        else
            # Check if monitor exists in current state
            $current_by_id[$cfg_monitor.id] as $curr_monitor |
            if $curr_monitor == null then
                # ID exists in config but not in Better Stack
                {action: "create_with_id", monitor: $cfg_monitor, note: "ID not found in Better Stack"}
            else
                # Compare monitors (excluding id and name)
                ($cfg_monitor | del(.id, .name)) as $cfg_clean |
                ($curr_monitor | del(.id, .name)) as $curr_clean |
                if $cfg_clean == $curr_clean then
                    {action: "unchanged", monitor: $cfg_monitor}
                else
                    {action: "update", monitor: $cfg_monitor, current: $curr_monitor, id: $cfg_monitor.id}
                end
            end
        end
    )) as $actions |

    # Group by action
    {
        to_create: ($actions | map(select(.action == "create" or .action == "create_with_id"))),
        to_update: ($actions | map(select(.action == "update"))),
        unchanged: ($actions | map(select(.action == "unchanged")))
    }
    ' > "$changes_file"

    echo "$changes_file"
}

dry_run_changes() {
    print_header "OPTION 2: Dry-Run (Preview Changes)"

    if [ ! -f "$CONFIG_FILE" ]; then
        print_error "Config file $CONFIG_FILE not found!"
        print_info "Please run Option 1 first to export current monitors"
        return 1
    fi

    print_info "Loading config file..."
    local config_monitors=$(jq '.monitors | length' "$CONFIG_FILE")
    print_success "Loaded $config_monitors monitors from config"

    print_info "Fetching current state from Better Stack..."
    local temp_current="/tmp/betterstack_current_$$.json"

    # Fetch and transform current monitors to same format as config
    fetch_all_monitors | jq '{
        monitors: [
            .[] | {
                id: .id,
                url: .attributes.url,
                name: .attributes.pronounceable_name,
                monitor_type: .attributes.monitor_type,
                monitor_group_id: .attributes.monitor_group_id,
                team_name: .attributes.team_name,
                check_frequency: .attributes.check_frequency,
                request_timeout: .attributes.request_timeout,
                recovery_period: .attributes.recovery_period,
                confirmation_period: .attributes.confirmation_period,
                http_method: .attributes.http_method,
                verify_ssl: .attributes.verify_ssl,
                follow_redirects: .attributes.follow_redirects,
                remember_cookies: .attributes.remember_cookies,
                call: .attributes.call,
                sms: .attributes.sms,
                email: .attributes.email,
                push: .attributes.push,
                critical_alert: .attributes.critical_alert,
                paused: .attributes.paused,
                regions: .attributes.regions,
                expected_status_codes: .attributes.expected_status_codes,
                request_headers: .attributes.request_headers,
                request_body: .attributes.request_body,
                required_keyword: .attributes.required_keyword,
                port: .attributes.port
            }
        ]
    }' > "$temp_current"

    print_info "Comparing config with current state..."
    local changes_file=$(compare_monitors "$CONFIG_FILE" "$temp_current")

    # Display results
    local create_count=$(jq '.to_create | length' "$changes_file" 2>/dev/null || echo "0")
    local update_count=$(jq '.to_update | length' "$changes_file" 2>/dev/null || echo "0")
    local unchanged_count=$(jq '.unchanged | length' "$changes_file" 2>/dev/null || echo "0")

    print_header "DRY-RUN SUMMARY"
    printf "${GREEN}Unchanged:${NC} %s monitors\n" "${unchanged_count:-0}"
    printf "${YELLOW}To Update:${NC} %s monitors\n" "${update_count:-0}"
    printf "${BLUE}To Create:${NC} %s monitors\n" "${create_count:-0}"
    echo ""

    # Show monitors to create
    if [ "${create_count:-0}" -gt 0 ]; then
        print_header "MONITORS TO CREATE ($create_count)"
        jq -r '.to_create[] |
            "  • \(.monitor.name // "unnamed")\n    URL: \(.monitor.url)\n    Type: \(.monitor.monitor_type)\n"' \
            "$changes_file"
    fi

    # Show monitors to update
    if [ "${update_count:-0}" -gt 0 ]; then
        print_header "MONITORS TO UPDATE ($update_count)"
        jq -r '.to_update[] |
            "  • [\(.id)] \(.monitor.name // "unnamed")\n    URL: \(.monitor.url)"' \
            "$changes_file"

        echo ""
        print_info "To see detailed field changes, check the changes file or add verbose mode"
    fi

    print_header "End of Dry-Run"

    # Ask if user wants to apply changes
    local total=$((create_count + update_count))
    if [ "$total" -gt 0 ]; then
        echo ""
        print_warning "$total change(s) detected."
        echo ""
        echo "Do you want to apply these changes?"
        echo "  1) Yes, apply changes now"
        echo "  2) No, return to menu"
        echo ""
        read -p "Select option (1-2): " apply_choice

        case $apply_choice in
            1)
                echo ""
                apply_changes "$changes_file"
                rm -f "$temp_current" "$changes_file"
                ;;
            2)
                print_info "No changes applied. Returning to menu..."
                rm -f "$temp_current" "$changes_file"
                ;;
            *)
                print_error "Invalid option. No changes applied."
                rm -f "$temp_current" "$changes_file"
                ;;
        esac
    else
        print_success "No changes needed. All monitors are up to date!"
        rm -f "$temp_current" "$changes_file"
    fi
}

################################################################################
# Apply changes functions
################################################################################

update_monitor() {
    local monitor_id="$1"
    local config_data="$2"

    # Extract fields to update (exclude id and name)
    local payload=$(echo "$config_data" | jq '{
        url: .url,
        monitor_type: .monitor_type,
        monitor_group_id: .monitor_group_id,
        check_frequency: .check_frequency,
        request_timeout: .request_timeout,
        recovery_period: .recovery_period,
        confirmation_period: .confirmation_period,
        http_method: .http_method,
        verify_ssl: .verify_ssl,
        follow_redirects: .follow_redirects,
        remember_cookies: .remember_cookies,
        call: .call,
        sms: .sms,
        email: .email,
        push: .push,
        critical_alert: .critical_alert,
        paused: .paused,
        regions: .regions,
        expected_status_codes: .expected_status_codes,
        request_headers: .request_headers,
        request_body: .request_body,
        required_keyword: .required_keyword,
        port: .port
    }')

    # API call to update monitor
    response=$(curl -s -X PATCH \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$BASE_URL/monitors/$monitor_id")

    # Check if update was successful
    if echo "$response" | jq -e '.data.id' >/dev/null 2>&1; then
        return 0
    else
        echo "$response" >&2
        return 1
    fi
}

create_monitor() {
    local config_data="$1"

    # Extract fields for creation (remove IDs from request_headers)
    local payload=$(echo "$config_data" | jq '{
        url: .url,
        pronounceable_name: .name,
        monitor_type: .monitor_type,
        monitor_group_id: .monitor_group_id,
        check_frequency: .check_frequency,
        request_timeout: .request_timeout,
        recovery_period: .recovery_period,
        confirmation_period: .confirmation_period,
        http_method: .http_method,
        verify_ssl: .verify_ssl,
        follow_redirects: .follow_redirects,
        remember_cookies: .remember_cookies,
        call: .call,
        sms: .sms,
        email: .email,
        push: .push,
        critical_alert: .critical_alert,
        paused: .paused,
        regions: .regions,
        expected_status_codes: .expected_status_codes,
        request_headers: (.request_headers | map({name: .name, value: .value})),
        request_body: .request_body,
        required_keyword: .required_keyword,
        port: .port
    }')

    # API call to create monitor
    response=$(curl -s -X POST \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$BASE_URL/monitors")

    # Check if creation was successful
    if echo "$response" | jq -e '.data.id' >/dev/null 2>&1; then
        echo "$response" | jq -r '.data.id'
        return 0
    else
        echo "$response" >&2
        return 1
    fi
}

apply_changes() {
    local changes_file="$1"

    print_header "APPLYING CHANGES"

    local create_count=$(jq '.to_create | length' "$changes_file")
    local update_count=$(jq '.to_update | length' "$changes_file")
    local total=$((create_count + update_count))

    if [ "$total" -eq 0 ]; then
        print_success "No changes to apply!"
        return 0
    fi

    local success_count=0
    local fail_count=0

    # Apply updates
    if [ "$update_count" -gt 0 ]; then
        print_info "Updating $update_count monitor(s)..."

        while IFS= read -r update; do
            local monitor_id=$(echo "$update" | jq -r '.id')
            local monitor_name=$(echo "$update" | jq -r '.monitor.name // "unnamed"')

            printf "  Updating [%s] %s... " "$monitor_id" "$monitor_name"

            if update_monitor "$monitor_id" "$(echo "$update" | jq -c '.monitor')"; then
                printf "${GREEN}✓${NC}\n"
                success_count=$((success_count + 1))
            else
                printf "${RED}✗${NC}\n"
                fail_count=$((fail_count + 1))
            fi
        done < <(jq -c '.to_update[]' "$changes_file")
    fi

    # Apply creations
    if [ "$create_count" -gt 0 ]; then
        print_info "Creating $create_count monitor(s)..."

        while IFS= read -r creation; do
            local monitor_name=$(echo "$creation" | jq -r '.monitor.name // "unnamed"')

            printf "  Creating %s... " "$monitor_name"

            new_id=$(create_monitor "$(echo "$creation" | jq -c '.monitor')")
            if [ $? -eq 0 ]; then
                printf "${GREEN}✓${NC} (ID: %s)\n" "$new_id"
                success_count=$((success_count + 1))
            else
                printf "${RED}✗${NC}\n"
                fail_count=$((fail_count + 1))
            fi
        done < <(jq -c '.to_create[]' "$changes_file")
    fi

    # Summary
    print_header "APPLICATION RESULTS"
    printf "${GREEN}Successful:${NC} %d/%d\n" "$success_count" "$total"
    printf "${RED}Failed:${NC} %d/%d\n" "$fail_count" "$total"
}

################################################################################
# Main Menu
################################################################################

show_menu() {
    clear
    print_header "Better Stack Monitor Management"
    echo "1) Export all monitors to config.json"
    echo "2) Update monitors from config.json"
    echo "3) Exit"
    echo ""
    read -p "Select an option (1-3): " choice

    case $choice in
        1)
            export_monitors
            ;;
        2)
            dry_run_changes
            ;;
        3)
            print_info "Goodbye!"
            exit 0
            ;;
        *)
            print_error "Invalid option. Please select 1-3."
            sleep 2
            show_menu
            ;;
    esac

    # Return to menu after operation
    echo ""
    read -p "Press Enter to return to menu..."
    show_menu
}

################################################################################
# Entry Point
################################################################################

# Check dependencies
if ! command -v jq &> /dev/null; then
    print_error "jq is required but not installed."
    print_info "Install it with: brew install jq (macOS) or apt-get install jq (Linux)"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    print_error "curl is required but not installed."
    exit 1
fi

# Check API token
if [ -z "$API_TOKEN" ]; then
    print_error "Better Stack API token not found!"
    echo ""
    print_info "Please set the API token using one of these methods:"
    echo ""
    echo "  1. Environment variable:"
    echo "     export BETTERSTACK_API_TOKEN='your-token-here'"
    echo ""
    echo "  2. Create a .env file:"
    echo "     echo 'BETTERSTACK_API_TOKEN=your-token-here' > .env"
    echo ""
    exit 1
fi

# Start the menu
show_menu
