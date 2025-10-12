declare module "node:url" {
  /**
   * Minimal declaration for Vite config compatibility when @types/node is not available.
   */
  export function fileURLToPath(url: string | URL): string;
  export class URL {
    constructor(input: string, base?: string | URL);
  }
}
