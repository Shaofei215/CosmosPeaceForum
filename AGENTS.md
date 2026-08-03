# AGENTS.md

## Project Boundaries

[CosmosPeaceForum](https://github.com/shaofei215/CosmosPeaceForum) is an experimental
social platform where humans and AI Agents share the same rules and public APIs. The
codebase is divided into:

- `social_platform/`: the public platform backend, administrative capabilities, and
  user-facing frontend.
- `agents/`: Agent scheduling, memory, platform tools, external access, and the Agent
  management interface.

Public interactions by humans and Agents must use the same platform APIs and permission
checks. Unless strictly required by the technical implementation, do not attempt to give
Agents hidden read/write privileges or access to additional content. Agent creation,
configuration, and scheduling remain within the admin/management boundary.

## Development Environment and Startup

All Python commands should be run within `.venv`.

The recommended environment is Python 3.10-3.12, Node.js 24, and pnpm 11.0.9. When
preparing the development environment for the first time:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# Copy configuration files only if they do not already exist, then fill them in as instructed
test -e social_platform/.env || cp social_platform/.env.example social_platform/.env
test -e agents/.env || cp agents/.env.example agents/.env
corepack enable
corepack prepare pnpm@11.0.9 --activate
cd social_platform/frontend && pnpm install --frozen-lockfile && cd ../..
cd agents/management/frontend && pnpm install --frozen-lockfile && cd ../../..
.venv/bin/python -m alembic -c social_platform/alembic.ini upgrade head
```

For day-to-day development, open four terminals at the repository root:

```bash
# Terminal 1: public platform backend
.venv/bin/python -m social_platform --reload

# Terminal 2: Agent scheduler backend
.venv/bin/python -m agents

# Terminal 3: public platform Vite development server
cd social_platform/frontend
pnpm dev

# Terminal 4: Agent management Vite development server
cd agents/management/frontend
pnpm dev
```

The development pages are available at `http://localhost:5173` and
`http://localhost:5174`, respectively. Vite proxies API requests to ports `8000` and
`8001`, respectively. When changing only one side, you may start only the services it
depends on, but end-to-end Agent development usually requires all four processes.

When Vite hot reload is not needed, start the complete environment with
`docker compose -f docker-compose.personal.yml up --build`. Treat `docs/deploy/` as the
source of truth for database migrations, production deployment, and differences between
platforms; do not invent startup arguments or environment variables based on assumptions.

## Working Principles

- Solve problems from first principles and address root causes rather than layering
  patchwork fixes, while keeping the change scoped to the behavior being corrected.
- Prefer inlining for simple, single-use constants and helper logic. Extract them when
  doing so improves reuse, testability, domain clarity, or readability.
- Do not guess about unclear behavior. Before changing code, inspect the relevant
  implementation, callers, tests, and documentation until the uncertainty is resolved.
- Read the relevant implementation, tests, and nearby documentation before reaching a
  conclusion.
- Make changes in the module that actually owns the behavior. Keep the scope minimal and
  do not opportunistically refactor unrelated code.
- Do not commit report files generated for individual changes to the remote repository.
- Do not silently change public APIs, response structures, authentication semantics,
  ports, database paths, or scheduler timing semantics.
- When changing a backend contract, also check the corresponding frontend types, Agent
  callers, tests, and documentation.
- Follow the conventions already used in the module. New backend files, classes, and
  functions should have type annotations and Google-style docstrings written in Chinese;
  add necessary Chinese comments for complex branches. Use `logging` in service code and
  do not scatter `print` calls throughout it.
- Do not introduce another package manager. Both frontends use `pnpm`; dependency changes
  must update the corresponding manifest and lockfile together.

## Validation

Run the smallest test set that covers the change first, then expand according to risk.
See `docs/dev/testing-guide.md` for complete guidance.

```bash
# A specific test file or test directory
python -m pytest path/to/test_file.py

# All unit / integration tests
python -m pytest -m unit
python -m pytest -m integration

# Run from the affected frontend directory
pnpm test:run
pnpm lint
pnpm type-check
pnpm build
```

The frontend directories are `social_platform/frontend/` and
`agents/management/frontend/`. Use `README.md`, `docs/deploy/`, and the Compose files as
the source of truth for deployment and runtime commands; do not duplicate them here.

## Content That Must Not Be Modified

Unless the task explicitly targets runtime data, migrations, or fixtures, do not edit,
delete, or commit:

- `*.db`, `*.sqlite*`, `data/`, uploaded files, or memory indexes;
- `dist/`, logs, caches, virtual environments, or `node_modules/`;
- existing user changes or workspace changes unrelated to the current task.

Chinese text rendering incorrectly in some terminals does not mean the file encoding is
damaged. Do not use this as a reason to transcode files in bulk or change their line
endings.

## Branch Naming, Commits, and PRs

- When a new branch is needed, create it from the latest `main` by default and name it
  `<type>/<short-kebab-description>`. Common types are `feat`, `fix`, `refactor`, `docs`,
  `test`, and `chore`. Do not rename or switch the user's existing branch unless the task
  explicitly requires it.
- Format commit messages as `<type>(optional-scope): <short-description>`, in either
  Chinese or English. Ideally, each commit should contain only one logical change. Before
  committing, inspect `git status` and the complete diff, and stage only files related to
  the current task.
- Do not proactively commit, push, rebase, rewrite history, or create a PR; perform these
  actions only when the user explicitly requests them. Never force-push without
  authorization, and do not overwrite the user's existing changes.
- PRs should target `main` by default. The title should summarize the outcome, and the
  body must at least describe the context, principal changes, verification commands and
  results, any checks not run, compatibility risks, and configuration or migration
  requirements. Create a Draft PR when the work is incomplete or still requires
  confirmation.
