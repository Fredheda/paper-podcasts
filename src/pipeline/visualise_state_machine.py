from pathlib import Path

from statemachine.contrib.diagram import DotGraphMachine

from .paper_workflow import PaperWorkflow

asset_dir = Path("assets")
asset_dir.mkdir(exist_ok=True)

audio_filename = "state_machine_visualisation.png"
audio_path = asset_dir / audio_filename

machine = PaperWorkflow()
dot = DotGraphMachine(machine)() 
dot.write_png(str(audio_path))