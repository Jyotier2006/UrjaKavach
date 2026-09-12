import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';
export default defineConfig([...nextVitals, ...nextTs, {rules:{'react-hooks/set-state-in-effect':'off','react-hooks/immutability':'off','react-hooks/purity':'off','react-hooks/refs':'off'}}, globalIgnores(['out/**','.next/**','next-env.d.ts'])]);
