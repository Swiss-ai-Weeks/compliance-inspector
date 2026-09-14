# Ecosystem

```mermaid
flowchart LR
  Human[Participant / Developer]
  Agent[Antigravity AI Agent]
  LocalApp[Compliance Inspector App / Streamlit]
  GPUMachine[GPU Server · cosmos3-nano-reasoner]
  Notepad[Shared Participant Notepad]
  UpstreamRepo[GitHub · Swiss-ai-Weeks/compliance-inspector]
  Datasets[Datasets · HATREC / Assembly101 / IKEA]

  Human --> LocalApp
  Human -- SSH --> GPUMachine
  Human -- Collaborate --> Notepad
  Agent --> LocalApp
  Agent --> UpstreamRepo
  LocalApp -- Ingests --> Datasets
  LocalApp -- REST / NIM API --> GPUMachine
```

## Entities
- **Local Application**: Streamlit dashboard + video processing + compliance engine.
- **GPU Server**: Hosts the `cosmos3-nano-reasoner` container / NIM.
- **Shared Notepad**: Collaboration point between hackathon participants.
- **GitHub Upstream**: `https://github.com/Swiss-ai-Weeks/compliance-inspector`.
- **Reference Datasets**: HATREC, Assembly101, IKEA Manuals at Work.
