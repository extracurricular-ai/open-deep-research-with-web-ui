from config import load_config
from run import create_agent

from smolagents.gradio_ui import GradioUI

agent = create_agent(load_config())

demo = GradioUI(agent)

if __name__ == "__main__":
    demo.launch()
