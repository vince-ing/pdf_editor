// tools.js — Tool registry. Add new tools here and they propagate everywhere.

export const TOOLS = {
    SELECT:    'select',
    TEXT:      'text',
    HIGHLIGHT: 'highlight',
    REDACT:    'redact',
    CROP:      'crop',
    // Scaffolded — wire up when backend supports
    // LINK:   'link',
    // STAMP:  'stamp',
    // SHAPE:  'shape',
};

export const TOOL_ICONS = {
    [TOOLS.SELECT]:    { icon: '↖', label: 'Select',    key: 'V' },
    [TOOLS.TEXT]:      { icon: 'T',  label: 'Text',      key: 'T' },
    [TOOLS.HIGHLIGHT]: { icon: '▬', label: 'Highlight', key: 'H' },
    [TOOLS.REDACT]:    { icon: '■', label: 'Redact',    key: 'R' },
    [TOOLS.CROP]:      { icon: '⬚', label: 'Crop',      key: 'C' },
};

export const TOOL_CURSORS = {
    [TOOLS.SELECT]:    'default',
    [TOOLS.TEXT]:      'text',
    [TOOLS.HIGHLIGHT]: 'crosshair',
    [TOOLS.REDACT]:    'crosshair',
    [TOOLS.CROP]:      'crosshair',
};