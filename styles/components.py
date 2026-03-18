COMPONENTS_CSS = """<style>
.stMetric{background:var(--color-surface);padding:1rem;border-radius:var(--radius-md);border:1px solid var(--color-border);box-shadow:var(--shadow-sm) !important}
.stMetric label,.stMetric [data-testid="stMetricLabel"]{color:var(--color-text-secondary) !important}
.stMetric [data-testid="stMetricValue"]{color:var(--color-text) !important;font-family:var(--font-family-mono) !important;font-variant-numeric:tabular-nums !important}
div[data-testid="stExpander"]{background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius-md)}
h1,h2,h3{color:var(--color-text) !important;letter-spacing:var(--letter-spacing-tight)}

@keyframes skeleton-pulse{
    0%{background-position:-200px 0}
    100%{background-position:calc(200px + 100%) 0}
}
.skeleton-loader{
    background:linear-gradient(90deg,var(--color-bg-secondary) 25%,var(--color-surface-hover) 50%,var(--color-bg-secondary) 75%);
    background-size:200px 100%;
    animation:skeleton-pulse 1.5s ease-in-out infinite;
    border-radius:var(--radius-sm);height:80px;margin:0.5rem 0;
}

@keyframes toast-in{0%{transform:translateX(100%);opacity:0}100%{transform:translateX(0);opacity:1}}
@keyframes toast-out{0%{opacity:1}100%{opacity:0;transform:translateY(-20px)}}
.archon-toast{
    position:fixed;top:1rem;right:1rem;z-index:99999;
    padding:0.8rem 1.2rem;border-radius:var(--radius-sm);
    font-size:0.9rem;font-weight:500;
    animation:toast-in 0.3s ease-out,toast-out 0.3s ease-in 2.7s forwards;
    box-shadow:var(--shadow-lg);pointer-events:none;
}
.archon-toast.success{background:var(--color-success);color:var(--color-text-inverse)}
.archon-toast.error{background:var(--color-danger);color:var(--color-text-inverse)}
.archon-toast.info{background:var(--color-primary);color:var(--color-text-inverse)}

@media(max-width:768px){
.stMetric{background:var(--color-surface) !important;border:1px solid var(--color-border) !important;border-radius:var(--radius-md) !important;padding:0.8rem !important;margin-bottom:0.4rem !important}
[data-testid="stExpander"]{border:1px solid var(--color-border) !important;border-radius:var(--radius-md) !important;margin-bottom:0.4rem !important}
[data-testid="stExpander"] summary{padding:0.8rem !important;font-size:0.95rem !important}
.stButton>button{border-radius:var(--radius-md) !important;font-weight:600 !important}
.stSelectbox>div>div,.stTextInput>div>div,.stNumberInput>div>div{border-radius:var(--radius-sm) !important;font-size:16px !important}
}

/* Card surface styles */
.stMetric,.stForm,[data-testid="stExpander"]>details{
    background:var(--color-surface) !important;
    border:1px solid var(--color-border) !important;
    border-radius:var(--radius-md) !important;
    backdrop-filter:none !important;
    -webkit-backdrop-filter:none !important;
}

.stMetric{transition:border-color var(--transition-normal),box-shadow var(--transition-normal) !important}
.stMetric:hover{border-color:var(--color-primary) !important;box-shadow:var(--shadow-md) !important}
.stMetric [data-testid="stMetricValue"]{font-weight:700 !important}

/* Buttons */
.stButton>button[kind="primary"]{
    background:var(--color-primary) !important;
    border:1px solid var(--color-primary-hover) !important;
    color:var(--color-text-inverse) !important;
    box-shadow:var(--shadow-md) !important;
    transition:all var(--transition-fast) !important;
}
.stButton>button[kind="primary"]:hover{
    background:var(--color-primary-hover) !important;
    box-shadow:var(--shadow-lg) !important;
    transform:translateY(-1px) !important;
}
.stButton>button:not([kind="primary"]){
    background:var(--color-bg-secondary) !important;
    color:var(--color-text) !important;
    border:1px solid var(--color-border) !important;
}

/* Tabs styling */
.stTabs [data-baseweb="tab"][aria-selected="true"]{
    background:linear-gradient(135deg,var(--color-primary-light),transparent) !important;
    border-bottom:2px solid var(--color-primary) !important;
    color:var(--color-primary) !important;
    font-weight:600 !important;
}
.stTabs [data-baseweb="tab"]{
    transition:all var(--transition-fast) !important;
    border-radius:var(--radius-sm) var(--radius-sm) 0 0 !important;
}

/* Sidebar active page */
[data-testid="stSidebarNav"] a[aria-current="page"]{
    background:linear-gradient(90deg,var(--color-primary-light),transparent) !important;
    border-left:3px solid var(--color-primary) !important;
    font-weight:700 !important;
    color:var(--color-primary) !important;
}

/* Inputs */
.stTextInput>div>div,.stSelectbox>div>div,.stNumberInput>div>div,.stTextArea>div>div{
    background:var(--color-bg) !important;
    border:1px solid var(--color-border) !important;
    border-radius:var(--radius-md) !important;
    transition:border-color var(--transition-fast) !important;
}
.stTextInput>div>div:focus-within,.stSelectbox>div>div:focus-within,.stNumberInput>div>div:focus-within,.stTextArea>div>div:focus-within{
    border-color:var(--color-primary) !important;
    box-shadow:0 0 0 3px rgba(59,130,246,0.1) !important;
}

/* Expander */
[data-testid="stExpander"]>details>summary{
    border-radius:var(--radius-lg) !important;
    transition:background var(--transition-fast) !important;
}
[data-testid="stExpander"]>details>summary:hover{
    background:var(--color-primary-light) !important;
}

/* Dataframe styling */
.stDataFrame [data-testid="stDataFrameResizable"]{
    border-radius:var(--radius-md) !important;
    border:1px solid var(--color-border) !important;
    overflow:hidden !important;
}

.stDataFrame table{font-variant-numeric:tabular-nums !important}

/* Spinner custom */
.stSpinner>div{
    border-top-color:var(--color-primary) !important;
}

/* Scrollbar */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--color-primary);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--color-primary-hover)}
</style>"""
