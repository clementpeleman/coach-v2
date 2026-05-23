import { mkdir, rm, copyFile } from 'node:fs/promises';
import * as esbuild from 'esbuild';

await esbuild.build({
  entryPoints: ['src/bootstrap.jsx'],
  outfile: 'src/app.bundle.js',
  bundle: true,
  format: 'iife',
  target: ['es2019'],
  minify: true,
  legalComments: 'none',
  jsx: 'transform',
});

await rm('dist', { recursive: true, force: true });
await mkdir('dist/src', { recursive: true });
await copyFile('index.html', 'dist/index.html');
await copyFile('src/app.bundle.js', 'dist/src/app.bundle.js');
