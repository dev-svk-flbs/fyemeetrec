#!/usr/bin/env python3
"""
Test script to demonstrate internal meeting filtering logic
"""

def is_internal_only_meeting(event):
    """Check if meeting has only @fyelabs.com participants"""
    all_emails = []
    
    # Get organizer email
    if event.get('organizer'):
        organizer_data = event['organizer']
        if isinstance(organizer_data, dict):
            organizer_email = organizer_data.get('emailAddress', {}).get('address', '')
            if organizer_email:
                all_emails.append(organizer_email.lower())
    
    # Get attendees emails
    if event.get('requiredAttendees'):
        attendees = [email.strip().lower() for email in event['requiredAttendees'].split(';') if email.strip()]
        all_emails.extend(attendees)
    
    if event.get('optionalAttendees'):
        optional = [email.strip().lower() for email in event['optionalAttendees'].split(';') if email.strip()]
        all_emails.extend(optional)
    
    # Remove duplicates
    all_emails = list(set(all_emails))
    
    # Check if ALL participants are @fyelabs.com
    if all_emails:
        return all(email.endswith('@fyelabs.com') for email in all_emails)
    
    return False  # If no participant data, include the meeting


# Test cases
test_meetings = [
    {
        "subject": "Internal Team Sync",
        "organizer": {"emailAddress": {"address": "souvik@fyelabs.com"}},
        "requiredAttendees": "alice@fyelabs.com; bob@fyelabs.com",
        "expected": True,  # Should be filtered (internal only)
        "reason": "All participants are @fyelabs.com"
    },
    {
        "subject": "Client Meeting",
        "organizer": {"emailAddress": {"address": "souvik@fyelabs.com"}},
        "requiredAttendees": "alice@fyelabs.com; client@external.com",
        "expected": False,  # Should NOT be filtered (has external)
        "reason": "Has external participant"
    },
    {
        "subject": "Sales Call",
        "organizer": {"emailAddress": {"address": "sales@fyelabs.com"}},
        "requiredAttendees": "prospect@company.com",
        "expected": False,  # Should NOT be filtered
        "reason": "External prospect"
    },
    {
        "subject": "Product Demo",
        "organizer": {"emailAddress": {"address": "demo@fyelabs.com"}},
        "requiredAttendees": "user1@fyelabs.com; user2@fyelabs.com",
        "optionalAttendees": "external@partner.com",
        "expected": False,  # Should NOT be filtered
        "reason": "Has optional external attendee"
    },
    {
        "subject": "All Hands Internal",
        "organizer": {"emailAddress": {"address": "ceo@fyelabs.com"}},
        "requiredAttendees": "team1@fyelabs.com; team2@fyelabs.com; team3@fyelabs.com",
        "expected": True,  # Should be filtered
        "reason": "All internal team members"
    }
]

print("=" * 80)
print("INTERNAL MEETING FILTER TEST")
print("=" * 80)

passed = 0
failed = 0

for i, meeting in enumerate(test_meetings, 1):
    result = is_internal_only_meeting(meeting)
    expected = meeting['expected']
    status = "✅ PASS" if result == expected else "❌ FAIL"
    
    if result == expected:
        passed += 1
    else:
        failed += 1
    
    print(f"\nTest {i}: {meeting['subject']}")
    print(f"  Organizer: {meeting.get('organizer', {}).get('emailAddress', {}).get('address', 'N/A')}")
    print(f"  Required: {meeting.get('requiredAttendees', 'None')}")
    print(f"  Optional: {meeting.get('optionalAttendees', 'None')}")
    print(f"  Expected: {'Internal-only (filter)' if expected else 'Keep (has external)'}")
    print(f"  Result: {'Internal-only (filter)' if result else 'Keep (has external)'}")
    print(f"  Reason: {meeting['reason']}")
    print(f"  Status: {status}")

print("\n" + "=" * 80)
print(f"TEST SUMMARY: {passed} passed, {failed} failed out of {len(test_meetings)} tests")
print("=" * 80)

if failed == 0:
    print("✅ All tests passed! Internal meeting filter is working correctly.")
else:
    print(f"❌ {failed} test(s) failed. Please review the logic.")
