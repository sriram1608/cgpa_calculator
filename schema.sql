DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS marks;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL
);

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
