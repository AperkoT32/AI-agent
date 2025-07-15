from core.agent import AIAgent
from plugins.example_api import API_model

def main():
    agent = AIAgent()
    agent.start()
    try:
        API_model(agent)
    finally:
        agent.stop()

if __name__ == "__main__":
    main()
