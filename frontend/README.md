# ReviewLens AI Frontend

Initial frontend scaffold using Next.js 14 App Router, TypeScript, Tailwind CSS, and shadcn/ui conventions.

## Run locally

```bash
npm install
npm run dev
```

Open http://localhost:3000.

Run with Docker from monorepo root:

```bash
docker compose up --build frontend backend db
```

## Test

```bash
npm test
```

Run tests from Docker container:

```bash
docker compose exec frontend npm test
```
