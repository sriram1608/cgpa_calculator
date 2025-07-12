-- Drop old tables if needed (optional for development/reset)
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS marks;

-- Users table: stores student and admin credentials
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    password TEXT NOT NULL,
    department TEXT NOT NULL,
    graduation_year TEXT NOT NULL,
    role TEXT NOT NULL  -- 'student' or 'admin'
);

-- Marks table: stores semester-wise marks per student
CREATE TABLE IF NOT EXISTS marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment TEXT NOT NULL,      -- student's email
    semester INTEGER NOT NULL,
    credits INTEGER NOT NULL,
    grade_point REAL NOT NULL
);
