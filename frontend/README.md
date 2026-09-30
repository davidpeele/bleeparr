# Bleeparr frontend

React interface for the FastAPI application in `../backend`.

```sh
npm ci
npm run dev
```

The development server proxies `/api` to `http://127.0.0.1:5050`.
For production, `npm run build` writes `dist`, which the backend serves directly.
Run `npm run lint` before submitting changes. No external font or image services are required.
