# Local chat in VS Code

Install Ollama from https://ollama.com/download/windows, then run:

```powershell
ollama pull qwen3:1.7b
ollama pull all-minilm
```

Keep Ollama running. A.R.C. uses its local API at `127.0.0.1:11434`.
The chat model writes conversational answers from retrieved project records;
source cards let you inspect the supporting evidence. Model answers can be
incorrect, so inspect the records when accuracy matters. If Ollama is unavailable,
chat falls back to recorded evidence and displays a notice.

Reload the extension with **Developer: Reload Window**. Try:

- `What was my most recent change 12:30am onwards?`
- `What changed yesterday?`
- `Create a project`
- `Enable observation`
- `Pause observation`
- `Capture Git changes`
- `Index pending memory`
- `Create a checkpoint`
- `Run tests`

Enabling observation from chat opens its permission popup immediately. Other
action requests show buttons; click one to run the corresponding A.R.C. command.
All commands remain available through **Ctrl+Shift+P**. Register Project adds
the open Git folder to A.R.C., without scaffolding an application. Connect it
after registration. Observation must be enabled for automatic recording.

Times use the editor's local timezone. A time without a day means today;
`most recent` and `latest` return one matching record. `Oldest`, `earliest`, and
`first change` return the earliest matching record across all recorded history,
unless the question includes a day or time filter. `Before` and `until`
use an exclusive upper time bound; `from`, `after`, and `onwards` currently use
an inclusive lower time bound. Day queries support today and yesterday.
