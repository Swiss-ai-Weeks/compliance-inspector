# Visual compliance inspector

### Summary of instructions
Can AI tell whether a procedure was actually followed? Build a system that watches a video of a real-world process and determines whether the required steps were completed correctly.

For example, it could analyze a maintenance task, identify which steps were performed or missed, and indicate when they happened. The challenge is about understanding activities over time rather than simply recognizing objects or individual images.

### Build instructions
Build a video-based compliance inspector that analyzes footage of a worker or industrial process and determines whether required actions have been completed correctly.

For example, given an operating procedure and a video of a maintenance task, the system could identify which steps were completed, which were missed, and when each relevant event occurred.

**Participants should explore temporal understanding rather than treating the problem as simple image classification.**

Suggested technologies include **VSS** (**Video Search and Summarization**) and **NVIDIA Cosmos NIMs**.
Suggested datasets:
* https://www.kaggle.com/datasets/ayoznur/hatrec-video-dataset,
* https://assembly-101.github.io/
* https://github.com/yunongLiu1/IKEA-Manuals-at-Work
