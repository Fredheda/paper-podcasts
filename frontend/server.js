import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { createProxyMiddleware } from 'http-proxy-middleware';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'http://ca-podcasts-agent';

// Security headers
app.use((req, res, next) => {
  res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  next();
});

// Proxy API + health requests to the internal-only backend container app.
// http-proxy-middleware v3+ requires the mount path baked into `target`.
// Unlike Portfolio's single-endpoint JSON proxy, this backend has several
// routes (search/jobs/library/chat) including an SSE stream
// (/api/chat/stream) -- a generic reverse proxy handles all of that (method,
// content-type, and streaming) natively, where hand-rolled fetch forwarding
// would not.
app.use('/api', createProxyMiddleware({ target: `${BACKEND_URL}/api`, changeOrigin: true }));
app.use('/health', createProxyMiddleware({ target: `${BACKEND_URL}/health`, changeOrigin: true }));

// Serve static files from the dist directory
app.use(express.static(path.join(__dirname, 'dist')));

// SPA fallback: serve index.html for all routes (React Router support)
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
