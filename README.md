# Attend50: Intelligent Student Attendance Tracker

#### Video Demo: <URL HERE>

#### Description:
**Attend50** is a full-stack, responsive web application engineered to solve a common dilemma faced by university students: monitoring institutional attendance criteria, projecting future safe skip margins, and preventing attendance debarment.

Many universities enforce strict mandatory attendance minimums (such as 75% or 80%). Standard spreadsheets or generic logging apps force students to manually calculate ratios or guess how missing an upcoming lecture might impact their standing. Attend50 eliminates guesswork by integrating a real-time mathematical decision engine directly into a daily attendance dashboard. In addition to standard session tracking, it calculates dynamic **"bunk cushions"** (the exact number of future lectures a student can safely skip while staying above their target) and **"recovery runs"** (the consecutive lectures they must attend to restore their eligibility if they fall into the danger zone).

---

### Core Features

1. **User Authentication & Session Management:**
   * Multi-user architecture with isolated relational data.
   * Secure credential hashing via `werkzeug.security` (`scrypt` algorithm) to protect user passwords against plaintext breaches.
   * Server-side session tracking with custom `@login_required` route decorators.

2. **Course Onboarding & Mid-Semester Baseline Support:**
   * Configurable target percentages per course (e.g., 75% for lectures, 85% for practical labs).
   * Starting baseline inputs (`starting_held` and `starting_attended`) allow students to begin using the tracker mid-semester without retroactively creating dozens of artificial daily logs.

3. **Smart Margin Mathematical Engine:**
   * Automatically computes whether a student is in a **Safe Zone** or **Danger Zone**.
   * Employs real-time threshold calculations:
     * **Safe Buffer Formula:** $\lfloor \frac{A}{R} - H \rfloor$ (where $A$ is total attended classes, $H$ is total classes held, and $R$ is the required target ratio).
     * **Recovery Run Formula:** $\lceil \frac{R \cdot H - A}{1 - R} \rceil$ classes required consecutively without missing.

4. **1-Click Attendance Logger:**
   * Rapid dashboard interface enabling quick logging of `Present`, `Absent`, or `Cancelled` sessions with timestamps.
   * Instant recalculation of statistics upon submission.

5. **Visual Analytics via Chart.js:**
   * Interactive, responsive horizontal bar charts comparing current attendance percentage against target criteria for every enrolled course.
   * Visual status indicators dynamically styled using green and red thresholds.

6. **Historical Audit & Mistake Correction (`/history`):**
   * Filterable audit table sorting attendance logs by course or status (`Present`, `Absent`, `Cancelled`).
   * One-click deletion feature enabling students to undo mistaken entries with automatic database updates and recalculations.

---

### File Architecture and Implementation Details

* **`app.py`:**
  The central Flask controller for the entire application. It defines application configuration, sets up filesystem-backed session management, establishes the SQLite connection, and routes incoming HTTP requests:
  * `/register`, `/login`, `/logout`: Manage the authentication lifecycle, handling input validation, password hash comparisons, and clearing session states.
  * `/`: The dashboard route. It aggregates database records, merges baseline historical numbers with live logged tallies, calls `helpers.calculate_stats`, formats JSON payloads for Chart.js canvases, and renders `index.html`.
  * `/log`: Accepts fast POST payloads containing course IDs, dates, and attendance statuses.
  * `/courses` & `/courses/delete`: Handles the creation, validation, listing, and cascading deletion of academic courses.
  * `/history` & `/history/delete`: Implements multi-parameter SQL filtering to display past records and provides secure deletion logic ensuring users can only remove their own records.

* **`helpers.py`:**
  Contains standalone utility logic to ensure clean separation of concerns:
  * `apology(message, code)`: Renders user-friendly, formatted error responses for invalid form submissions or unauthorized actions.
  * `login_required(f)`: Custom Python decorator ensuring protected routes redirect unauthenticated users to `/login`.
  * `calculate_stats(attended, held, target_percentage)`: The core mathematical engine of Attend50. It prevents zero-division errors, calculates current percentage rates, and computes both margin buffers and recovery thresholds.

* **`attendance.db`:**
  A relational SQLite database configured with primary keys, foreign keys, and integrity rules. It consists of three relational tables:
  * `users`: Stores user identity records (`id`, `username`, `hash`).
  * `courses`: Stores subject configurations linked to a user via `user_id`, including course codes, names, targets, and initial baseline metrics.
  * `attendance_records`: Stores individual attendance actions with foreign keys to both `users` and `courses`, storing timestamps and status strings.

* **`templates/` Directory:**
  * `layout.html`: The foundational Jinja2 skeleton. Integrates the Bootswatch Zephyr CSS theme, Bootstrap 5 JavaScript bundle, Bootstrap Icons, and Chart.js CDN. It conditionally renders the top navigation bar depending on session status and injects flashed alerts.
  * `index.html`: The dashboard view. Renders overall cumulative attendance metrics, Chart.js analytical charts, individual subject cards with smart margin banners, and quick 1-click attendance buttons.
  * `courses.html`: Management view for adding courses via modal dialogs, viewing baseline stats, and deleting subjects.
  * `history.html`: Filterable tabular interface for auditing past logs and deleting misclicks.
  * `login.html` & `register.html`: Clean, card-based authentication forms with validation feedback.
  * `apology.html`: CS50-styled error presentation template.

* **`static/styles.css`:**
  Custom styling that complements the Bootswatch theme with refined card shadows, custom badge borders, and responsive mobile enhancements.

* **`requirements.txt`:**
  Specifies the core external Python dependencies (`Flask`, `Flask-Session`, `cs50`, `Werkzeug`) necessary to install and run the application in any standard Python environment.

---

### Key Design Decisions

1. **Handling "Cancelled" Classes:**
   College lectures are frequently cancelled due to faculty absence, strikes, or holidays. Logging a cancelled class must neither penalize nor artificially inflate attendance percentages. Attend50 logs `Cancelled` status for record-keeping and audit history, but programmatically excludes these sessions from both total held and total attended tallies.

2. **Mid-Semester Baseline Onboarding:**
   Students rarely start using an attendance app on day one of a semester. Forcing a student to click "Present" 40 times to recreate their current standing would ruin user experience. Storing `starting_held` and `starting_attended` directly in the `courses` table cleanly solves this problem without bloating the transaction table.

3. **Client-Side Visual Rendering vs. Server-Side Images:**
   Rather than generating static charts on the backend (e.g., with Matplotlib) and writing images to disk, Attend50 serializes calculated numbers into JSON arrays in `app.py` and feeds them to Chart.js on the frontend. This ensures animations are smooth, reduces server overhead, and keeps the user interface responsive across mobile devices.
