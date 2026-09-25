export interface AppConfig {
  maxRetries: number;
  timeoutMs: number;
}

export const defaultConfig: AppConfig = {
  maxRetries: 3,
  timeoutMs: 2000,
};
