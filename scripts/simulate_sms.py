#!/usr/bin/env python3
"""
SMS Simulation Script for Barbershop Autopilot
Simulates SMS conversations without needing live Twilio credentials.
"""
import requests
import json
import argparse
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8001"  # Change to your backend URL

def simulate_inbound_sms(from_number: str, to_number: str, body: str):
    """Simulate an inbound SMS via the Twilio webhook endpoint"""
    webhook_url = f"{BASE_URL}/api/webhooks/twilio/inbound"
    
    # Twilio-like form data
    form_data = {
        "From": from_number,
        "To": to_number,
        "Body": body,
        "MessageSid": f"SM{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "AccountSid": "SIMULATION",
        "NumMedia": "0"
    }
    
    print(f"\n📱 Sending SMS from {from_number}:")
    print(f"   '{body}'")
    
    try:
        response = requests.post(webhook_url, data=form_data)
        result = response.json()
        print(f"   ✅ Response: {result}")
        return result
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def run_demo_conversation():
    """Run a demo conversation simulating a client booking"""
    shop_number = "+15551234567"  # Demo shop number
    client_number = "+15559999999"  # Simulated client number
    
    print("\n" + "="*60)
    print("🎭 BARBERSHOP AUTOPILOT - SMS SIMULATION")
    print("="*60)
    print(f"Shop Number: {shop_number}")
    print(f"Client Number: {client_number}")
    print("="*60)
    
    conversations = [
        ("Hi, I'd like to book a haircut", "Initial contact"),
        ("BOOK", "Request booking flow"),
        ("1", "Select first service"),
        ("HELP", "Request help menu"),
        ("STATUS", "Check appointment status"),
        ("CONFIRM", "Confirm appointment"),
    ]
    
    for message, description in conversations:
        print(f"\n--- {description} ---")
        simulate_inbound_sms(client_number, shop_number, message)
        input("Press Enter to continue...")
    
    print("\n" + "="*60)
    print("✅ Demo conversation complete!")
    print("="*60)


def interactive_mode():
    """Run in interactive mode for custom testing"""
    shop_number = "+15551234567"
    
    print("\n" + "="*60)
    print("🎭 BARBERSHOP AUTOPILOT - INTERACTIVE SMS SIMULATION")
    print("="*60)
    print(f"Shop Number: {shop_number}")
    print("Enter 'quit' to exit")
    print("="*60)
    
    client_number = input("\nEnter client phone number (or press Enter for default): ").strip()
    if not client_number:
        client_number = "+15559999999"
    
    print(f"Using client number: {client_number}")
    
    while True:
        message = input("\n📱 Enter message (or 'quit'): ").strip()
        if message.lower() == 'quit':
            break
        
        simulate_inbound_sms(client_number, shop_number, message)
    
    print("\n👋 Goodbye!")


def test_all_commands():
    """Test all available SMS commands"""
    shop_number = "+15551234567"
    client_number = "+15558888888"
    
    commands = ["HELP", "BOOK", "STATUS", "CANCEL", "RESCHEDULE", "CONFIRM"]
    
    print("\n" + "="*60)
    print("🧪 TESTING ALL SMS COMMANDS")
    print("="*60)
    
    for cmd in commands:
        print(f"\n--- Testing: {cmd} ---")
        simulate_inbound_sms(client_number, shop_number, cmd)
    
    print("\n✅ All commands tested!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SMS Simulation for Barbershop Autopilot")
    parser.add_argument("--mode", choices=["demo", "interactive", "test"], default="demo",
                        help="Simulation mode (default: demo)")
    parser.add_argument("--url", default="http://localhost:8001",
                        help="Backend API URL (default: http://localhost:8001)")
    
    args = parser.parse_args()
    BASE_URL = args.url
    
    if args.mode == "demo":
        run_demo_conversation()
    elif args.mode == "interactive":
        interactive_mode()
    elif args.mode == "test":
        test_all_commands()
