import { defineConfig, loadEnv } from 'vite';
import type { ProxyOptions } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

// 선택한 개발 서버만 동일 출처로 프록시하며 API의 CORS·인증 설정은 바꾸지 않는다.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), 'VITE_');
  const target = env.VITE_API_PROXY_TARGET;
  const paths = ['/api', '/v1', '/geoserver', '/healthz', '/readyz', '/docs', '/openapi.json'];
  const proxy: Record<string, ProxyOptions> = {};
  if (env.VITE_RESULTS_PROXY_TARGET) {
    const resultTarget = new URL(env.VITE_RESULTS_PROXY_TARGET);
    if (resultTarget.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(resultTarget.hostname) || resultTarget.href !== resultTarget.origin + '/') {
      throw new Error('VITE_RESULTS_PROXY_TARGET must be a local HTTP origin');
    }
    // Keep browser Host/Origin paired. The result API also checks the loopback peer.
    proxy['^/api/common-results(?:/|\\?|$)'] = {
      target: resultTarget.origin,
      changeOrigin: false,
      rewrite: path => path.replace(/^\/api\/common-results(?=\/|\?|$)/, '/api/results'),
    };
  }
  if (target) for (const path of paths) proxy[path] = { target, changeOrigin: true };
  return {
    plugins: [react()],
    server: { proxy },
  };
});
