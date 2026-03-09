// src/types/textProps.ts

export interface TextRun {
  text:       string;
  bold?:      boolean;
  italic?:    boolean;
  fontFamily?: string;
  fontSize?:  number;
  color?:     string;
}

export interface TextProps {
  fontFamily: string;
  fontSize:   number;
  color:      string;
  isBold:     boolean;
  isItalic:   boolean;
}

export const DEFAULT_TEXT_PROPS: TextProps = {
  fontFamily: 'Helvetica',
  fontSize:   12,
  color:      '#000000',
  isBold:     false,
  isItalic:   false,
};

// UI font name → fitz fontname. Only built-in PDF fonts reliably available in PyMuPDF.
// Bold/italic variants are handled by the isBold/isItalic flags → fitz font suffix.
export const FONT_TO_FITZ: Record<string, string> = {
  'Helvetica':       'helv',
  'Times New Roman': 'tiro',
  'Courier':         'cour',
};

export const FONT_TO_CSS: Record<string, string> = {
  'Helvetica':       'Helvetica, Arial, sans-serif',
  'Times New Roman': '"Times New Roman", Times, serif',
  'Courier':         '"Courier New", Courier, monospace',
};

export const FONT_OPTIONS = Object.keys(FONT_TO_FITZ);