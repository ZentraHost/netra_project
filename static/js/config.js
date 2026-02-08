/**
 * NETRA - Config & State
 */

export const CONFIG = {
    scanInterval: 1000,
    microInterval: 200,
    imgWidth: 480,
    jpegQuality: 0.4
};

export const STATE = {
    active: false,
    debug: false,
    ws: null,
    loop: null,
    heading: 0,
    lastShake: 0,
    mode: 'nav',
    lastGeiger: 0,
    wsRetryCount: 0
};
