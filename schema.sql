DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS marks;

CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    name TEXT,
    password TEXT,
    department TEXT,
    graduation_year TEXT,
    role TEXT
)

CREATE TABLE students (
    enrollment TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT NOT NULL,
    FOREIGN KEY (username) REFERENCES users(username)
);

CREATE TABLE marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment TEXT NOT NULL,
    semester INTEGER NOT NULL,
    credits INTEGER NOT NULL,
    grade_point INTEGER NOT NULL,
    FOREIGN KEY (enrollment) REFERENCES students(enrollment)
);
