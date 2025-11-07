#!/bin/bash

# Configuration
API_TOKEN="aeZ3tcXRJe5ZsMpkBRf5LCWR" # Replace with your Better Stack API token
BASE_URL="https://betteruptime.com/api/v2"

# Global flags for bulk operations
BULK_YES=false
BULK_NO=false

# Color codes for better visual output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Professional separators (without color)
HEADER_SEP="--------------------------------------------------------------------------------"
SECTION_SEP="--------------------------------------------------------------------------------"
ITEM_SEP="--------------------------------------------------------------------------------"

# Print formatted header
print_header() {
    echo -e "$HEADER_SEP"
    echo -e "|                    ${CYAN}BETTER STACK MONITOR CREATION TOOL${NC}                    |"
    echo -e "$HEADER_SEP"
}

# Print section separator
print_section() {
    local title="$1"
    echo -e "\n$SECTION_SEP"
    echo -e "  ${PURPLE}${title}${NC}"
    echo -e "$SECTION_SEP"
}

# Print item separator
print_item_separator() {
    echo -e "${YELLOW}$ITEM_SEP${NC}"
}
# Print success message
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Print error message
print_error() {
    echo -e "${RED}✗ Error: $1${NC}"
}

# Print warning message
print_warning() {
    echo -e "${YELLOW}⚠ Warning: $1${NC}"
}

# Print info message
print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# Enhanced confirmation prompt with bulk options
confirm_action() {
    local message="$1"
    local default="${2:-n}"
    local allow_bulk="${3:-true}"
    local prompt

    # Check bulk flags first
    if [ "$BULK_YES" = true ]; then
        print_info "Auto-confirming: $message (bulk yes mode)"
        return 0
    elif [ "$BULK_NO" = true ]; then
        print_info "Auto-declining: $message (bulk no mode)"
        return 1
    fi

    if [ "$default" = "y" ]; then
        if [ "$allow_bulk" = "true" ]; then
            prompt="[Y/n/ya/na]"
        else
            prompt="[Y/n]"
        fi
    else
        if [ "$allow_bulk" = "true" ]; then
            prompt="[y/N/ya/na]"
        else
            prompt="[y/N]"
        fi
    fi

    while true; do
        if [ "$allow_bulk" = "true" ]; then
            echo -e "${YELLOW}${message} ${prompt} (ya=yes to all, na=no to all):${NC} \c"
        else
            echo -e "${YELLOW}${message} ${prompt}:${NC} \c"
        fi
        read -r response

        # Use default if empty response
        if [ -z "$response" ]; then
            response="$default"
        fi

        # Convert to lowercase for easier matching
        response_lower=$(echo "$response" | tr '[:upper:]' '[:lower:]')

        case "$response_lower" in
        y | yes)
            return 0
            ;;
        n | no)
            return 1
            ;;
        ya | yesall | "yes all")
            if [ "$allow_bulk" = "true" ]; then
                BULK_YES=true
                print_success "Enabled 'Yes to All' mode for remaining confirmations"
                return 0
            else
                print_error "Bulk operations not allowed for this prompt."
            fi
            ;;
        na | noall | "no all")
            if [ "$allow_bulk" = "true" ]; then
                BULK_NO=true
                print_success "Enabled 'No to All' mode for remaining confirmations"
                return 1
            else
                print_error "Bulk operations not allowed for this prompt."
            fi
            ;;
        "")
            # Handle empty input (just Enter pressed) - use default
            case "$default" in
            y | Y)
                return 0
                ;;
            n | N)
                return 1
                ;;
            esac
            ;;
        *)
            if [ "$allow_bulk" = "true" ]; then
                print_error "Please enter 'y' for yes, 'n' for no, 'ya' for yes to all, or 'na' for no to all."
            else
                print_error "Please enter 'y' for yes or 'n' for no."
            fi
            ;;
        esac
    done
}

# Determine config file path
determine_config_path() {

    CONFIG_FILE="./betterstack/config.json"

}

# Validate configuration file
validate_config_file() {
    print_section "CONFIGURATION VALIDATION"

    # Check if config file exists
    if [ ! -f "$CONFIG_FILE" ]; then
        print_error "Configuration file $CONFIG_FILE not found"
        print_info "Ensure config.json is in ./src/uptime-betterstack/ relative to $(pwd), or provide a valid path"
        exit 1
    fi
    print_success "Configuration file found: $CONFIG_FILE"

    # Check if config file is JSON
    if [[ "$CONFIG_FILE" != *.json ]]; then
        print_error "Only .json files are supported"
        print_info "Use a file with .json extension"
        exit 1
    fi
    print_success "Configuration file has valid JSON extension"

    # Parse config file
    CONFIG_JSON=$(jq . "$CONFIG_FILE" 2>/dev/null)
    if [ $? -ne 0 ]; then
        print_error "Failed to parse configuration file $CONFIG_FILE"
        print_info "Please check JSON syntax"
        exit 1
    fi
    print_success "Configuration file parsed successfully"
}

# Extract and validate configuration data
extract_config_data() {
    print_section "CONFIGURATION DATA EXTRACTION"

    # Get GroupName
    GROUP_NAME=$(echo "$CONFIG_JSON" | jq -r '.GroupName // empty' 2>/dev/null)
    if [ -z "$GROUP_NAME" ]; then
        print_error "GroupName not found in $CONFIG_FILE"
        exit 1
    fi
    print_success "Group Name: $GROUP_NAME"

    # Get environments
    ENVS=$(echo "$CONFIG_JSON" | jq -r '.envs[]' 2>/dev/null)
    if [ -z "$ENVS" ]; then
        print_error "No environments found in $CONFIG_FILE"
        exit 1
    fi
    print_success "Environments found: $(echo "$ENVS" | tr '\n' ', ' | sed 's/,$//')"

    # Get default monitor settings
    DEFAULT_SETTINGS=$(echo "$CONFIG_JSON" | jq -c '.default_monitor_settings' 2>/dev/null)
    if [ -z "$DEFAULT_SETTINGS" ]; then
        print_error "No default_monitor_settings found in $CONFIG_FILE"
        exit 1
    fi
    print_success "Default monitor settings loaded"

    # Get endpoints
    ENDPOINTS=$(echo "$CONFIG_JSON" | jq -c '.endpoints[]' 2>/dev/null)
    if [ -z "$ENDPOINTS" ]; then
        print_error "No endpoints found in $CONFIG_FILE"
        exit 1
    fi

    local endpoint_count=$(echo "$ENDPOINTS" | wc -l)
    print_success "Endpoints found: $endpoint_count"
}

# Display configuration summary
display_config_summary() {
    print_section "CONFIGURATION SUMMARY"

    echo -e "${CYAN}Group Name:${NC} $GROUP_NAME"

    echo -e "${CYAN}Environments:${NC}"
    for env in $ENVS; do
        echo -e "  • $env"
    done

    echo -e "${CYAN}Endpoints:${NC}"
    while IFS= read -r endpoint_json; do
        path=$(echo "$endpoint_json" | jq -r '.path // empty')
        shouldCall=$(echo "$endpoint_json" | jq -r '.shouldCall // false')
        if [ -n "$path" ]; then
            echo -e "  • $path ${YELLOW}(call: $shouldCall)${NC}"
        fi
    done <<<"$ENDPOINTS"

    local total_monitors=0
    local env_count=$(echo "$ENVS" | wc -l)
    local endpoint_count=$(echo "$ENDPOINTS" | wc -l)
    total_monitors=$((env_count * endpoint_count))

    echo -e "\n${PURPLE}Total monitors to be created: $total_monitors${NC}"

    # Debug info
    echo -e "${CYAN}Debug: Found $env_count environments and $endpoint_count endpoints${NC}"
}

# Create a monitor
create_monitor() {
    local env="$1"
    local endpoint_json="$2"

    # Extract endpoint fields
    path=$(echo "$endpoint_json" | jq -r '.path // empty')
    shouldCall=$(echo "$endpoint_json" | jq -r '.shouldCall // false')
    endpoint_settings=$(echo "$endpoint_json" | jq -c '.monitor_settings // {}')
    name=$(echo "$endpoint_json" | jq -r 'if .pronouncation_name and .pronouncation_name != "" then .pronouncation_name else .path end')

    # Validate path
    if [ -z "$path" ]; then
        print_warning "Skipping endpoint with missing path"
        return
    fi

    # Construct URL and pronounceable name
    url="https://${env}${path}"
    pronounceable_name="${GROUP_NAME} - ${name}"

    print_item_separator
    echo -e "${CYAN}Monitor Details:${NC}"
    echo -e "  URL: ${BLUE}$url${NC}"
    echo -e "  Call Enabled: ${YELLOW}$shouldCall${NC}"
    echo -e "  PronouncationName: ${BLUE}${GROUP_NAME} - ${name}"

    # Enhanced confirmation prompt
    if ! confirm_action "Create this monitor?" "y" "true"; then
        print_info "Skipped monitor creation for $url"
        return 1 # Return 1 to indicate skipped
    fi

    # Merge default and endpoint-specific settings
    merged_settings=$(jq -c --argjson default "$DEFAULT_SETTINGS" --argjson endpoint "$endpoint_settings" \
        '$default * $endpoint' <<<'{}')

    # Override call with shouldCall
    merged_settings=$(jq -c --argjson call "$shouldCall" '. + {call: $call}' <<<"$merged_settings")

    # Build payload
    payload=$(jq -c \
        --arg url "$url" \
        --arg name "$pronounceable_name" \
        '. + {url: $url, pronounceable_name: $name}' <<<"$merged_settings")

    print_info "Creating monitor..."

    # Send POST request
    response=$(curl -s -X POST \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$BASE_URL/monitors")

    # Check response
    if echo "$response" | jq . >/dev/null 2>&1; then
        monitor_id=$(echo "$response" | jq -r '.data.id // "unknown"')
        created_url=$(echo "$response" | jq -r '.data.attributes.url // "unknown"')
        created_name=$(echo "$response" | jq -r '.data.attributes.pronounceable_name // "unknown"')

        if [ "$monitor_id" != "unknown" ]; then
            print_success "Monitor created successfully!"
            echo -e "  ${CYAN}ID:${NC} $monitor_id"
            echo -e "  ${CYAN}Name:${NC} $created_name"
            echo -e "  ${CYAN}URL:${NC} $created_url"
            return 0 # Return 0 for success
        else
            print_error "Monitor creation failed - Invalid response structure"
            echo -e "${RED}Response:${NC} $response"
            return 2 # Return 2 for API error
        fi
    else
        print_error "Monitor creation failed"
        echo -e "${RED}Response:${NC} $response"
        return 2 # Return 2 for API error
    fi
}

# Main execution logic
main() {
    print_header
    # Step 2: Determine and validate config file
    determine_config_path "$1"
    validate_config_file

    # Step 3: Extract configuration data
    extract_config_data

    # Step 4: Display summary and get final confirmation
    display_config_summary

    print_item_separator
    if ! confirm_action "Proceed with monitor creation?" "n" "false"; then
        print_info "Operation cancelled by user"
        exit 0
    fi

    print_section "MONITOR CREATION PROCESS"

    local created_count=0
    local skipped_count=0
    local failed_count=0

    # Iterate over environments and endpoints
    for env in $ENVS; do
        echo -e "\n${PURPLE}Processing environment: ${env}${NC}"

        # Convert ENDPOINTS to array to avoid subshell issues
        local endpoints_array=()
        while IFS= read -r line; do
            endpoints_array+=("$line")
        done <<<"$ENDPOINTS"

        # Process each endpoint
        for endpoint_json in "${endpoints_array[@]}"; do
            path=$(echo "$endpoint_json" | jq -r '.path // empty')
            if [ -z "$path" ]; then
                continue
            fi

            echo -e "${CYAN}Processing endpoint: $path${NC}"

            # Call create_monitor and capture return code
            create_monitor "$env" "$endpoint_json"
            result=$?

            case $result in
            0)
                ((created_count++))
                echo -e "${GREEN}✓ Created: $path${NC}"
                ;;
            1)
                ((skipped_count++))
                echo -e "${YELLOW}⚠ Skipped: $path${NC}"
                ;;
            2)
                ((failed_count++))
                echo -e "${RED}✗ Failed: $path${NC}"
                ;;
            esac

        done
    done

    # Final summary
    print_section "OPERATION SUMMARY"
    print_success "Monitors created: $created_count"
    print_warning "Monitors skipped: $skipped_count"
    print_error "Monitors failed: $failed_count"

    print_header
    print_success "Monitor creation process completed!"
}

# Execute main function
main "$@"
