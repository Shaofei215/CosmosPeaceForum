/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly PLATFORM_DISPLAY_NAME?: string;
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
