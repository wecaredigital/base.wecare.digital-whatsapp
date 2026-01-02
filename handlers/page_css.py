# =============================================================================
# PAGE CSS - Minimal White Design
# =============================================================================
# Background: #FFF | Text: #000 | Borders: #000 (1px)
# Buttons: Black (#000) with white text, radius 13px (pill)
# No gradients, no gray fills
# 100% Mobile Responsive
# =============================================================================

CSS_BASE = '''
* { margin: 0; padding: 0; box-sizing: border-box; }
html { font-size: 16px; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #fff;
    color: #000;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    line-height: 1.5;
}
.card {
    background: #fff;
    border: 1px solid #000;
    border-radius: 16px;
    padding: 32px 24px;
    max-width: 400px;
    width: 100%;
    text-align: center;
}
.icon { font-size: 48px; margin-bottom: 16px; }
h1 { 
    color: #000; 
    font-size: 1.5rem; 
    font-weight: 600; 
    margin-bottom: 12px; 
}
p { color: #000; margin-bottom: 12px; font-size: 0.95rem; }
a { color: #000; text-decoration: underline; }
a:hover { text-decoration: none; }
.btn {
    display: inline-block;
    background: #000;
    color: #fff;
    border: none;
    padding: 14px 32px;
    font-size: 1rem;
    font-weight: 500;
    border-radius: 13px;
    cursor: pointer;
    width: 100%;
    text-decoration: none;
    transition: opacity 0.2s;
}
.btn:hover { opacity: 0.85; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
@media (max-width: 480px) {
    body { padding: 16px; }
    .card { padding: 24px 16px; border-radius: 12px; }
    h1 { font-size: 1.25rem; }
    .btn { padding: 12px 24px; }
}
'''

# Payment Page CSS
CSS_PAYMENT = CSS_BASE + '''
.amt { 
    font-size: 2.5rem; 
    font-weight: 700; 
    color: #000; 
    margin: 16px 0 8px;
}
.desc { 
    color: #000; 
    font-size: 0.9rem; 
    margin-bottom: 20px;
    opacity: 0.7;
}
.fee-box {
    border: 1px solid #000;
    border-radius: 8px;
    padding: 16px;
    margin: 20px 0;
    text-align: left;
    font-size: 0.85rem;
}
.fee-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
}
.fee-row.total {
    border-top: 1px solid #000;
    margin-top: 8px;
    padding-top: 12px;
    font-weight: 600;
}
.fee-label { color: #000; }
.fee-value { color: #000; font-weight: 500; }
.secure { 
    color: #000; 
    font-size: 0.75rem; 
    margin-top: 16px;
    opacity: 0.6;
}
.order-id { 
    color: #000; 
    font-size: 0.7rem; 
    margin-top: 8px;
    opacity: 0.5;
}
.error { 
    color: #000; 
    background: #fff;
    border: 1px solid #000;
    margin-top: 12px; 
    padding: 10px;
    border-radius: 8px;
    font-size: 0.85rem;
    display: none;
}
@media (max-width: 480px) {
    .amt { font-size: 2rem; }
    .fee-box { padding: 12px; }
}
'''

# Success Page CSS
CSS_SUCCESS = CSS_BASE + '''
.checkmark { color: #000; }
.pid { 
    color: #000; 
    font-size: 0.8rem; 
    word-break: break-all; 
    margin-top: 16px;
    padding: 12px;
    border: 1px solid #000;
    border-radius: 8px;
    font-family: monospace;
}
'''

# Error Page CSS
CSS_ERROR = CSS_BASE + '''
.error-msg {
    border: 1px solid #000;
    padding: 12px;
    border-radius: 8px;
    margin: 16px 0;
    font-size: 0.9rem;
}
'''

# 404 Page CSS (minimal - just for redirect message)
CSS_404 = CSS_BASE

# Short Link CSS
CSS_SHORTLINK = CSS_BASE + '''
.domain { 
    font-weight: 600;
    font-size: 1.1rem;
    margin-top: 8px;
}
'''

# Expired Link CSS
CSS_EXPIRED = CSS_BASE

# Test Link Created CSS
CSS_TEST_CREATED = CSS_PAYMENT + '''
.info {
    border: 1px solid #000;
    padding: 16px;
    border-radius: 8px;
    margin-top: 20px;
    text-align: left;
    font-size: 0.85rem;
}
.info strong { font-weight: 600; }
.info code {
    display: block;
    margin-top: 4px;
    word-break: break-all;
    font-family: monospace;
    font-size: 0.8rem;
}
'''
