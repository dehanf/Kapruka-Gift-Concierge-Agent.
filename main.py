"""
main.py — Kapruka Gift Concierge
Entry point for the CLI conversation loop.
"""

from agents.router import Router
import time



def main():
    print("=" * 50)
    print("  Kapruka Gift Concierge")
    print("=" * 50)

    customer_id = input("\nEnter your customer ID (or press Enter for 'guest'): ").strip()
    if not customer_id:
        customer_id = "guest"

    router = Router(customer_id=customer_id)

    print(f"\nWelcome! I'm your Kapruka gift concierge.")
    print("I can help you find gifts, save recipient preferences, and check delivery.")
    print("Type 'quit' or 'exit' to end the session.\n")
    print("-" * 50)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "bye"}:
            print("\nAssistant: Thank you for using Kapruka Gift Concierge. Goodbye!")
            break

        start = time.time()
        response = router.route(user_input)
        elapsed = time.time() - start
        print(f"\nAssistant: {response}")
        print(f"[Response time: {elapsed:.2f}s]")
        print("-" * 50)


if __name__ == "__main__":
    main()
