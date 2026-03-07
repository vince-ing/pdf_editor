export const TOOLS = {
    SELECT:    'select',
    TEXT:      'text',
    HIGHLIGHT: 'highlight',
    REDACT:    'redact',
};

export const TOOL_ICONS = {
    [TOOLS.SELECT]:    { icon: '↖', label: 'Select' },
    [TOOLS.TEXT]:      { icon: 'T',  label: 'Text' },
    [TOOLS.HIGHLIGHT]: { icon: '▬', label: 'Highlight' },
    [TOOLS.REDACT]:    { icon: '■', label: 'Redact' },
};

export const TOOL_CURSORS = {
    [TOOLS.SELECT]:    'default',
    [TOOLS.TEXT]:      'text',
    [TOOLS.HIGHLIGHT]: 'crosshair',
    [TOOLS.REDACT]:    'crosshair',
};