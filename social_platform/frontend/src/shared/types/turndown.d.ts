declare module 'turndown' {
  interface TurndownOptions {
    bulletListMarker?: '-' | '*' | '+';
    codeBlockStyle?: 'indented' | 'fenced';
    emDelimiter?: '_' | '*';
    headingStyle?: 'setext' | 'atx';
  }

  export default class TurndownService {
    constructor(options?: TurndownOptions);
    turndown(input: string | Node): string;
  }
}
