import os
import sys
import json
import time
import base64

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt
from rich import print as rprint

console = Console()

# ── Path resolution ────────────────────────────────────────────────────────────
# All paths are anchored to the directory that contains THIS script so the demo
# works regardless of where the user invokes Python from.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_VIDEO_DIR  = os.path.join(_SCRIPT_DIR, "data", "videos")
_SOP_DIR    = os.path.join(_SCRIPT_DIR, "data", "sops")
OUTPUT_DIR  = os.path.join(_SCRIPT_DIR, "output")


def _discover_videos():
    """
    Scan data/videos/ for .mp4 files and parse each filename to extract
    product type and model name.

    Convention:  video_{Type}_{...}_{Model}.mp4
      - Type  = second segment  (e.g. Bench, Chair, Table)
      - Model = last segment    (e.g. Tjusig, Applaro, Bekvam)
      - Middle segments are extra descriptors (e.g. "another")

    Returns a sorted list of dicts:
      {"path", "type", "model", "label", "sop_path" (or None)}
    """
    if not os.path.isdir(_VIDEO_DIR):
        console.print(f"[bold red]Video directory not found: {_VIDEO_DIR}[/bold red]")
        return []

    videos = []
    for fname in sorted(os.listdir(_VIDEO_DIR)):
        if not fname.lower().endswith(".mp4"):
            continue
        stem = os.path.splitext(fname)[0]          # e.g. "video_Bench_another_Tjusig"
        parts = stem.split("_")                     # ["video", "Bench", "another", "Tjusig"]
        if len(parts) < 3:
            continue  # doesn't match convention — skip

        vtype = parts[1]                            # "Bench"
        model = parts[-1]                           # "Tjusig"
        label = " ".join(parts[1:])                 # "Bench another Tjusig"

        sop_file = f"sop_{model.lower()}.json"
        sop_path = os.path.join(_SOP_DIR, sop_file)
        if not os.path.isfile(sop_path):
            sop_path = None

        videos.append({
            "path":     os.path.join(_VIDEO_DIR, fname),
            "type":     vtype,
            "model":    model.lower(),
            "label":    label,
            "sop_path": sop_path,
        })

    return videos


def _show_video_picker(videos, title="Available videos"):
    """Display a numbered list of discovered videos and return the chosen dict."""
    table = Table(title=title, show_header=True, header_style="bold magenta", expand=False)
    table.add_column("#", justify="center", style="bold green", no_wrap=True)
    table.add_column("Video", style="bold white")
    table.add_column("Product", style="cyan")
    table.add_column("SOP", justify="center")

    for i, v in enumerate(videos, start=1):
        sop_status = "[bold green]✅ found[/bold green]" if v["sop_path"] else f"[bold red]❌ create sop_{v['model']}.json[/bold red]"
        table.add_row(str(i), v["label"], v["type"], sop_status)

    console.print(table)
    choices = [str(i) for i in range(1, len(videos) + 1)]
    pick = Prompt.ask("Select video", choices=choices)
    return videos[int(pick) - 1]


def display_banner():
    banner = """
  [bold cyan]─── Visual compliance inspector ───[/bold cyan]
  [dim]Automated SOP Enforcement via NVIDIA Cosmos NIM and Nemotron (NemoClaw)[/dim]
    """
    console.print(Panel(banner, style="bold blue", expand=False))

def load_sop(sop_path):
    """Load an SOP JSON file. Returns the parsed dict or None if not found."""
    if sop_path and os.path.isfile(sop_path):
        with open(sop_path, "r") as f:
            return json.load(f)
    return None

def extract_frames_with_progress(video_path, num_frames=8, sample_fps=1):
    try:
        import cv2
        has_cv2 = True
    except ImportError:
        has_cv2 = False

    if not has_cv2 or not os.path.exists(video_path):
        if not has_cv2:
            console.print("[yellow]Note: opencv (cv2) not loaded in local environment. Simulating frame extraction...[/yellow]")
        else:
            console.print(f"[yellow]Video not found at {video_path}. Simulating frame extraction...[/yellow]")
        
        frames_data = []
        n = num_frames if num_frames else 12
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[yellow]Extracting & downsampling frames...", total=n)
            for i in range(n):
                time.sleep(0.08)
                frames_data.append({"timestamp_sec": round(i * 1.5, 2), "b64_image": "mock_b64"})
                progress.advance(task)
        console.print(f"[bold green]✓ Simulated extraction of {len(frames_data)} frames.[/bold green]")
        return frames_data

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames_data = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[yellow]Extracting & downsampling frames...", total=num_frames if num_frames else max(1, total_frames // 30))
        
        if num_frames:
            indices = [int(i * total_frames / num_frames) for i in range(num_frames)]
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret:
                    frame = cv2.resize(frame, (512, 512))
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    b64 = base64.b64encode(buf).decode("utf-8")
                    timestamp = round(idx / fps, 2)
                    frames_data.append({"timestamp_sec": timestamp, "b64_image": b64})
                progress.advance(task)
        else:
            step = int(fps / sample_fps) if sample_fps else 30
            idx = 0
            while cap.isOpened():
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if not ret or idx >= total_frames:
                    break
                frame = cv2.resize(frame, (512, 512))
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                b64 = base64.b64encode(buf).decode("utf-8")
                timestamp = round(idx / fps, 2)
                frames_data.append({"timestamp_sec": timestamp, "b64_image": b64})
                progress.advance(task)
                idx += step

    cap.release()
    console.print(f"[bold green]✓ Extracted {len(frames_data)} frames from video.[/bold green]")
    return frames_data

API_CHUNK_LIMIT = 10  # NVIDIA Cosmos API hard cap per request

def _cosmos_single_call(client, model, prompt, chunk):
    """
    Send one chunk of frames to the API.
    Returns a parsed dict {"observed_actions": [...]} or raises.
    """
    image_contents = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{f['b64_image']}"}}
        for f in chunk
    ]
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}] + image_contents}],
        max_tokens=4096,
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    raw = response.choices[0].message.content
    return json.loads(raw)

def _call_with_halving_retry(client, model, prompt, chunk):
    """
    Try sending `chunk` frames. If the API rejects due to payload size,
    halve the chunk and retry once. Returns response text or raises.
    """
    try:
        return _cosmos_single_call(client, model, prompt, chunk)
    except Exception as e:
        err = str(e).lower()
        # Payload / image count errors — halve and retry once
        if any(kw in err for kw in ("too many", "payload", "413", "limit", "image")):
            halved = chunk[: len(chunk) // 2]
            if not halved:
                raise
            console.print(
                f"[yellow]⚠ Chunk too large ({len(chunk)} frames) — retrying with {len(halved)} frames...[/yellow]"
            )
            return _cosmos_single_call(client, model, prompt, halved)
        raise  # Any other error propagates normally

def _merge_chunk_observations(chunk_dicts):
    """
    Merge observed_actions from multiple JSON chunk responses into one dict.
    Each chunk covers a different slice of the video, so the same step_id can
    appear in multiple chunks. Strategy: keep the first detected=True result
    for each step_id; fall back to the last seen result if never detected.
    Returns: {"observed_actions": [...]} sorted by step_id.
    """
    merged = {}
    for chunk in chunk_dicts:
        for obs in chunk.get("observed_actions", []):
            step_id = obs.get("step_id")
            if step_id is None:
                continue
            existing = merged.get(step_id)
            # Prefer detected=True; only overwrite if we don't have a detected entry yet
            if existing is None or (obs.get("detected") and not existing.get("detected")):
                merged[step_id] = obs
    return {"observed_actions": sorted(merged.values(), key=lambda x: x["step_id"])}


def run_cosmos_reasoning(frames, sop_data, is_mock=False):
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NGC_API_KEY")

    if is_mock or not api_key:
        if not is_mock and not api_key:
            console.print("[yellow]NVIDIA_API_KEY / NGC_API_KEY not detected. Using mock / demo mode (offline).[/yellow]")
        else:
            console.print("[yellow]Running in Mock Mode...[/yellow]")
        
        with console.status("[bold green]Cosmos Vision LLM analyzing visual sequence...[/bold green]", spinner="dots"):
            time.sleep(1.2)

        # Generate mock observations from the actual SOP steps.
        # Mark roughly the first 60% as detected so the audit exercises
        # both COMPLETED and MISSED paths regardless of product.
        steps = sop_data.get("expected_steps", [])
        cutoff = max(1, int(len(steps) * 0.6))
        mock_actions = []
        for i, step in enumerate(steps[:cutoff]):
            mock_actions.append({
                "step_id": step["step_id"],
                "detected": True,
                "start_sec": i * 10 + 2,
                "end_sec": i * 10 + 12,
                "visual_evidence": f"[MOCK] Observed: {step['name']}"
            })
        return {"observed_actions": mock_actions}

    try:
        from openai import OpenAI
        console.print("[cyan]Connecting to NVIDIA Cosmos Reasoner API...[/cyan]")
        client = OpenAI(
            base_url=os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            api_key=api_key
        )
        model = os.getenv("NIM_MODEL_NAME", "nvidia/cosmos3-nano-reasoner")

        video_duration = max((f.get("timestamp_sec", 0) for f in frames), default=0)
        sop_json       = json.dumps(sop_data, indent=2)

        # Split frames into chunks of API_CHUNK_LIMIT (max 10) to stay within
        # NVIDIA's per-request image cap. Each chunk is reasoned independently
        # and the structured JSON results are merged by _merge_chunk_observations.
        chunks = [frames[i:i + API_CHUNK_LIMIT] for i in range(0, len(frames), API_CHUNK_LIMIT)]
        console.print(
            f"[dim]Sending {len(frames)} frames in {len(chunks)} chunk(s) "
            f"(≤{API_CHUNK_LIMIT} frames each)...[/dim]"
        )

        chunk_results = []
        failed_chunks = 0

        for idx, chunk in enumerate(chunks, start=1):
            # Build a per-chunk prompt that tells the model exactly which time
            # window it is looking at. This prevents it from "completing" steps
            # it cannot see by anchoring it to the actual frame timestamps.
            chunk_start = chunk[0].get("timestamp_sec", 0)
            chunk_end   = chunk[-1].get("timestamp_sec", chunk_start)
            chunk_prompt = (
                "You are a STRICT industrial assembly compliance inspector.\n"
                f"You are analyzing {len(chunk)} video frames "
                f"from approximately {chunk_start:.1f}s to {chunk_end:.1f}s of an assembly video.\n\n"
                "STRICT RULES:\n"
                "1. Include a step if you see the action being performed OR clear visual evidence that it has been completed in these specific frames.\n"
                "2. If you are uncertain, omit the step entirely.\n"
                "3. If no steps are clearly visible, return {\"observed_actions\": []}.\n"
                "4. DO NOT use prior knowledge or training data to fill in steps "
                "you cannot directly observe.\n\n"
                f"SOP steps to verify:\n{sop_json}\n\n"
                "Respond ONLY with valid JSON — no prose, no markdown fences:\n"
                "{\"observed_actions\": ["
                "{\"step_id\": <int>, \"detected\": true, "
                "\"start_sec\": <float or null>, \"end_sec\": <float or null>, "
                "\"visual_evidence\": \"<describe the action you directly saw>\"}"
                "]}\n"
                "Only include entries for steps you directly observed being performed."
            )

            with console.status(
                f"[bold green]Cosmos Vision LLM — chunk {idx}/{len(chunks)} "
                f"({len(chunk)} frames, {chunk_start:.0f}s–{chunk_end:.0f}s)...[/bold green]",
                spinner="dots"
            ):
                try:
                    result = _call_with_halving_retry(client, model, chunk_prompt, chunk)
                    chunk_results.append(result)
                except Exception as chunk_err:
                    console.print(
                        f"[bold red]Chunk {idx} failed: {chunk_err}[/bold red]"
                    )
                    failed_chunks += 1


        if not chunk_results:
            console.print(
                "[bold red]All API chunks failed. Falling back to mock findings.[/bold red]"
            )
            return run_cosmos_reasoning(frames, sop_data, is_mock=True)

        if failed_chunks:
            console.print(
                f"[yellow]⚠ {failed_chunks} chunk(s) failed — audit covers partial results.[/yellow]"
            )

        # Merge all chunk dicts into one structured result — this is what run_audit parses
        merged = _merge_chunk_observations(chunk_results)

        # ── Temporal safety net ───────────────────────────────────────────────
        # Override any step the model claims occurs AFTER the video ends.
        # This mechanically catches hallucinated steps regardless of how
        # convincing the model's visual_evidence description sounds.
        for obs in merged.get("observed_actions", []):
            start = obs.get("start_sec")
            if start is not None and start > video_duration:
                obs["detected"]       = False
                obs["start_sec"]      = None
                obs["end_sec"]        = None
                obs["visual_evidence"] = (
                    f"Temporal override: claimed start ({start}s) exceeds "
                    f"video duration ({video_duration:.1f}s) — step not in footage"
                )

        return merged


    except Exception as e:
        console.print(f"[bold red]API setup failed: {e}. Falling back to mock findings.[/bold red]")
        return run_cosmos_reasoning(frames, sop_data, is_mock=True)


def run_audit(sop, observations):
    expected_steps = {s["step_id"]: s["name"] for s in sop.get("expected_steps", [])}
    
    audit_trail = []
    overall_status = "PASS"
    last_end = -1

    if isinstance(observations, dict) and "observed_actions" in observations:
        obs_list = observations["observed_actions"]
    else:
        obs_list = [
            {
                "step_id": s["step_id"],
                "detected": True,
                "start_sec": s["step_id"] * 10,
                "end_sec": (s["step_id"] * 10) + 8,
                "visual_evidence": f"Observed assembly for {s['name']}"
            }
            for s in sop.get("expected_steps", [])
        ]

    for obs in obs_list:
        step_id = obs["step_id"]
        step_name = expected_steps.get(step_id, f"Step {step_id}")
        detected = obs.get("detected", True)
        start_sec = obs.get("start_sec")
        end_sec = obs.get("end_sec")

        if not detected:
            status = "MISSED"
            overall_status = "FAIL"
        elif start_sec is not None and last_end > -1 and start_sec < last_end:
            status = "OUT_OF_ORDER"
            overall_status = "FAIL"
        else:
            status = "COMPLETED"
            last_end = end_sec if end_sec is not None else last_end

        audit_trail.append({
            "step_id": step_id,
            "name": step_name,
            "status": status,
            "window": f"{start_sec}s - {end_sec}s" if (detected and start_sec is not None) else "N/A",
            "evidence": obs.get("visual_evidence", "Observed via Cosmos NIM")
        })

    # !!!Completeness check — any SOP step the model never mentioned at all is MISSED.
    # This is the critical path for non-compliant videos: Cosmos only reports steps
    # it can see, so absent steps never appear in obs_list and would otherwise be
    # silently treated as PASS. Cross-reference against the full SOP here.
    observed_ids = {obs["step_id"] for obs in obs_list}
    for step_id, step_name in expected_steps.items():
        if step_id not in observed_ids:
            overall_status = "FAIL"
            audit_trail.append({
                "step_id": step_id,
                "name": step_name,
                "status": "MISSED",
                "window": "N/A",
                "evidence": "Step not observed in any video segment"
            })

    # Sort by step_id so the table always reads in procedure order
    audit_trail.sort(key=lambda x: x["step_id"])

    return {"overall_status": overall_status, "audit_trail": audit_trail}

def display_report(report, raw_llm_text=None):
    console.print("\n")
    verdict = report["overall_status"]
    verdict_style = "bold white on green" if verdict == "PASS" else "bold white on red"
    console.print(Panel(f"FINAL AUDIT VERDICT: [{verdict_style}]  {verdict}  [/{verdict_style}]", title="[bold]Audit Result[/bold]", expand=False))

    table = Table(title="SOP Compliance audit trail", show_header=True, header_style="bold magenta")
    table.add_column("Step ID", justify="center", style="cyan", no_wrap=True)
    table.add_column("Procedure step", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Time window", justify="center", style="dim")
    table.add_column("Visual evidence", style="italic gray70")

    for step in report["audit_trail"]:
        status = step["status"]
        if status == "COMPLETED":
            st_fmt = "[bold green][OK] COMPLETED[/bold green]"
        elif status == "MISSED":
            st_fmt = "[bold red][x] MISSED[/bold red]"
        else:
            st_fmt = "[bold yellow][WARNING!] OUT_OF_ORDER[/bold yellow]"

        table.add_row(
            str(step["step_id"]),
            step["name"],
            st_fmt,
            step["window"] or "-",
            step["evidence"]
        )

    console.print(table)

    if raw_llm_text:
        console.print(Panel(raw_llm_text, title="Cosmos / Nemotron LLM raw analysis", style="dim green"))

def langchain_agent_query(sop):
    task_name = sop.get("task_name", "assembly")
    console.print(Panel(f"[bold yellow]LangChain / AI agent interactive Query Mode[/bold yellow]\nAsk any question about SOP compliance for: {task_name}", expand=False))
    query = Prompt.ask("[bold cyan]Enter query for compliance agent[/bold cyan]", default=f"What steps are required for {task_name}?")
    
    steps_summary = "\n".join([f"{s['step_id']}. {s['name']}: {s['description']}" for s in sop.get("expected_steps", [])])
    
    with console.status("[bold cyan]Agent reasoning with Nemotron / LangChain...[/bold cyan]", spinner="simpleDots"):
        time.sleep(1)
        api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NGC_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)
                resp = client.chat.completions.create(
                    model="nvidia/nemotron-3.5-lightning-30b-a3b",
                    messages=[
                        {"role": "system", "content": f"You are a visual compliance assistant. SOP steps:\n{steps_summary}"},
                        {"role": "user", "content": query}
                    ]
                )
                answer = resp.choices[0].message.content
            except Exception as e:
                answer = f"Agent response: Under SOP rules for {task_name}:\n{steps_summary}\n\nQuery analyzed: '{query}'."
        else:
            answer = f"[Demo Agent Mode] Relevant SOP procedures found for {task_name}:\n{steps_summary}\n\nQuery analyzed: '{query}'."

    console.print(Panel(answer, title="🤖 LangChain agent output", style="bold cyan"))

def main_menu():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    while True:
        display_banner()

        videos = _discover_videos()
        if not videos:
            console.print("[bold red]No videos found in data/videos/. Add .mp4 files and retry.[/bold red]")
            break

        console.print("[bold]Select an option:[/bold]")
        console.print("  [bold green]1.[/bold green] 📹 Audit a video against its SOP")
        console.print("  [bold green]2.[/bold green] 🧪 Offline mock audit (no API key required)")
        console.print("  [bold green]3.[/bold green] 🤖 LangChain / LLM Agent query")
        console.print("  [bold green]4.[/bold green] 🚪 Exit\n")

        choice = Prompt.ask("Choice", choices=["1", "2", "3", "4"], default="1")

        if choice == "4":
            console.print("[bold cyan]Goodbye![/bold cyan]")
            break

        # All three options need a video + SOP selection
        video = _show_video_picker(videos)

        if not video["sop_path"]:
            console.print(
                f"\n[bold red]No SOP found for model '{video['model']}'.[/bold red]\n"
                f"[yellow]Create [bold]data/sops/sop_{video['model']}.json[/bold] and retry.[/yellow]"
            )
        else:
            sop = load_sop(video["sop_path"])
            task_name = sop.get("task_name", video["label"])
            console.print(f"\n[bold cyan]Product:[/bold cyan] {video['label']}")
            console.print(f"[bold cyan]SOP:[/bold cyan] {task_name} ({len(sop.get('expected_steps', []))} steps)\n")

            if choice == "1":
                frames = extract_frames_with_progress(video["path"], num_frames=None, sample_fps=1)
                obs = run_cosmos_reasoning(frames, sop)
                raw_text = obs if isinstance(obs, str) else None
                report = run_audit(sop, obs)
                display_report(report, raw_text)
            elif choice == "2":
                frames = extract_frames_with_progress(video["path"], num_frames=20)
                obs = run_cosmos_reasoning(frames, sop, is_mock=True)
                report = run_audit(sop, obs)
                display_report(report)
            elif choice == "3":
                langchain_agent_query(sop)

        console.print("\n[bold]Action complete. What would you like to do next?[/bold]")
        console.print("  [bold green]1.[/bold green] Continue to the main menu")
        console.print("  [bold green]2.[/bold green] Exit application")

        post_choice = Prompt.ask("Choice", choices=["1", "2"], default="1")

        if post_choice == "2":
            console.print("[bold cyan]Goodbye![/bold cyan]")
            break

        console.clear()

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]Exited by user.[/yellow]")
        sys.exit(0)