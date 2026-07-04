from aegis_mind.core.mind import Mind
from aegis_mind.utils.config import load_config

config = load_config("config.yaml")
mind = Mind(config)

print("Aegis Mind v12 ready!")
print("Type /help for commands.")

while True:
    try:
        user_input = input("\n> ").strip()
        if user_input.lower() in ["quit", "exit"]:
            print("Saving and exiting...")
            mind.close()
            break
        response = mind.perceive(user_input)
        print(response)
    except KeyboardInterrupt:
        break
