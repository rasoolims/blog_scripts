import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://rasoolims.github.io',
  base: '/delsharm',
  integrations: [sitemap()],
});