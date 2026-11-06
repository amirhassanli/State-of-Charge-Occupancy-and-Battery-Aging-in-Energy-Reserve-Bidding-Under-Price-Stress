documentclass[tikz,border=10pt]{standalone}
usepackage{tikz}
usetikzlibrary{shapes.geometric, arrows.meta, positioning, fit, backgrounds, calc, shadows}

\begin{document}
\begin{tikzpicture}[
    node distance=1.0cm and 1.5cm,
    box/.style={
        rectangle,
        draw=black,
        very thick,
        rounded corners=3mm,
        align=center,
        minimum width=3.6cm,
        minimum height=1.0cm,
        font=\sffamily\bfseries\small,
        drop shadow={opacity=0.15, shadow xshift=1mm, shadow yshift=-1mm}
    },
    boxwide/.style={
        box,
        minimum width=5.2cm,
        font=\sffamily\bfseries\small
    },
    boxcolor/.style={
        box,
        fill=#1!20,
        draw=#1!70!black,
        text=#1!80!black
    },
    arrow/.style={
        -{Stealth[length=3.5mm, width=2.8mm]},
        very thick,
        draw=black!70,
        line width=0.8pt
    },
    label/.style={
        font=\sffamily\itshape\small,
        text=black!60
    },
    group/.style={
        inner sep=5mm,
        rounded corners=4mm,
        draw=#1!50!black,
        fill=#1!5,
        dashed,
        very thick
    }
]

% ===== 1. INPUT: FOUR ERROR MARGINALS =====
\node[boxcolor={red}] (pv)   {PV Forecast Error};
\node[boxcolor={orange}, below=0.9cm of pv] (wind) {Wind Error};
\node[boxcolor={cyan}, below=0.9cm of wind] (load) {Load Error};
\node[boxcolor={blue}, below=0.9cm of load] (price) {Price Error};

% Left labels for marginal distributions
\node[left=0.3cm of pv, label, align=right] {$F_{PV}(e_{PV})$};
\node[left=0.3cm of wind, label, align=right] {$F_{W}(e_{W})$};
\node[left=0.3cm of load, label, align=right] {$F_{L}(e_{L})$};
\node[left=0.3cm of price, label, align=right] {$F_{P}(e_{P})$};

% ===== 2. PIT TRANSFORMATION =====
\node[boxcolor={purple}, right=2.8cm of pv, yshift=-1.35cm] (pit) 
    {PIT Transformation};
\node[above=0.15cm of pit, label, align=center] {$u_i = F_i(e_i)$};

% ===== 3. STUDENT-t COPULA =====
\node[boxcolor={teal}, right=2.2cm of pit] (copula) 
    {Student-$t$ Copula};
\node[above=0.15cm of copula, label, align=center] {$\mathcal{C}_{R,\nu}(u_1,u_2,u_3,u_4)$};

% ===== 4. SCENARIO GENERATION =====
\node[boxcolor={olive}, right=2.2cm of copula] (scenarios) 
    {5000 Joint Scenarios};
\node[above=0.15cm of scenarios, label, align=center] {$(e_{PV},e_W,e_L,e_P)_j$};

% ===== 5. TAIL PROTECTION + REDUCTION =====
\node[boxcolor={magenta}, right=2.4cm of scenarios] (reduce) 
    {Tail Protection \\ \& Scenario Reduction};
\node[above=0.15cm of reduce, label, align=center] {Statistical + Decision-Aware};

% ===== 6. OUTPUT SETS =====
\node[boxcolor={orange}, below right=0.7cm and 0.0cm of reduce] (k30) 
    {\textbf{K = 30}};
\node[boxcolor={teal}, right=0.3cm of k30] (k50) 
    {\textbf{K = 50}};
\node[boxcolor={blue}, right=0.3cm of k50] (k100) 
    {\textbf{K = 100}};

% ===== ARROWS: Marginals → PIT =====
\draw[arrow] (pv.east) -- ++(0.6,0) |- (pit.west);
\draw[arrow] (wind.east) -- ++(0.6,0) |- (pit.west);
\draw[arrow] (load.east) -- ++(0.6,0) |- (pit.west);
\draw[arrow] (price.east) -- ++(0.6,0) |- (pit.west);

% ===== ARROWS: Main Flow =====
\draw[arrow] (pit.east) -- (copula.west);
\draw[arrow] (copula.east) -- (scenarios.west);
\draw[arrow] (scenarios.east) -- (reduce.west);

% ===== ARROWS: Reduce → Outputs =====
\draw[arrow] (reduce.south) -- ++(0,-0.6) -| (k30.north);
\draw[arrow] (reduce.south) -- ++(0,-0.6) -| (k50.north);
\draw[arrow] (reduce.south) -- ++(0,-0.6) -| (k100.north);

% ===== LABEL FOR OUTPUTS =====
\node[below=0.2cm of k30.south, label, align=center, yshift=-0.3cm] 
    {Reduced Scenario Sets};

% ===== GROUPS =====
\begin{scope}[on background layer]
    \node[group={red}, fit=(pv)(wind)(load)(price)] (group1) {};
    \node[above=0.1cm of group1.north, label, align=center] 
        {Marginal Calibration (Conformal)};
    
    \node[group={purple}, fit=(pit)] (group2) {};
    
    \node[group={teal}, fit=(copula)] (group3) {};
    
    \node[group={olive}, fit=(scenarios)] (group4) {};
    
    \node[group={magenta}, fit=(reduce)] (group5) {};
\end{scope}

\end{tikzpicture}
\end{document}
