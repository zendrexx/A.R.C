# Local chat in VS Code

Install Ollama once from https://ollama.com/download/windows, then connect your
project in A.R.C. The extension starts installed Ollama in the background if
needed and asks once before downloading the selected embedding model (default
`all-minilm`). Choose an installed conversational model with **ARC: Select AI
Model** in the sidebar's **AI Models** section or Command Palette. No chat model
is assumed. **ARC: Download Model** offers a confirmed download if you need one.
Normal use needs no Terminal commands.
Automatic observation remains a separate initial opt-in. Approved projects
reconnect on the next VS Code startup and pending records are indexed automatically.

Set `arc.ollama.autoStart` to false to disable background startup. Use **A.R.C.:
Retry Local AI Setup** to reconsider a model download decision. A.R.C. reuses
existing servers and never terminates them. It uses the API at `127.0.0.1:11434`.
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
