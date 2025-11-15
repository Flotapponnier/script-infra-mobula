#!/bin/bash

# Simple test script to debug the export

API_TOKEN="aeZ3tcXRJe5ZsMpkBRf5LCWR"
BASE_URL="https://betteruptime.com/api/v2"
OUTPUT_FILE="monitors_config.json"

echo "Starting export test..."

page=1
all_monitors="[]"
temp_file="/tmp/betterstack_test_$$.json"

echo "Fetching page 1..."
response=$(curl -s -H "Authorization: Bearer $API_TOKEN" \
    "$BASE_URL/monitors?page=1&per_page=100")

echo "Response received, extracting data..."
echo "$response" | jq '.data | length'

monitors=$(echo "$response" | jq -c '.data')
echo "Monitors variable: ${monitors:0:100}..."

all_monitors=$(echo "$all_monitors" | jq -c ". + $monitors")
echo "All monitors length: $(echo "$all_monitors" | jq 'length')"

echo "Transforming to config format..."
config=$(echo "$all_monitors" | jq '{
    monitors: [
        .[] | {
            id: .id,
            url: .attributes.url,
            name: .attributes.pronounceable_name,
            monitor_type: .attributes.monitor_type,
            check_frequency: .attributes.check_frequency,
            call: .attributes.call,
            sms: .attributes.sms,
            email: .attributes.email,
            push: .attributes.push
        }
    ]
}')

echo "Config created, saving to file..."
echo "$config" | jq '.' > "$OUTPUT_FILE"

echo "File written. Checking contents..."
wc -l "$OUTPUT_FILE"
echo "First few lines:"
head -20 "$OUTPUT_FILE"

echo "Done!"
