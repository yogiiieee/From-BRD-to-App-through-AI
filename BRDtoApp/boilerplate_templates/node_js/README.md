# Node.js Express TypeScript Boilerplate

A clean, minimal, and production-ready Node.js Express TypeScript boilerplate.

## Features

- TypeScript with modern configuration
- Express.js web framework
- CORS support
- Environment variables with dotenv
- ESLint for code linting
- Hot reloading in development
- Production-ready configuration

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Copy `.env.example` to `.env` and customize as needed:
   ```bash
   cp .env.example .env
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Build for production:
   ```bash
   npm run build
   ```

5. Start in production mode:
   ```bash
   npm start
   ```

## Available Scripts

- `npm run dev`: Start development server with hot reloading
- `npm run build`: Compile TypeScript to JavaScript
- `npm start`: Start production server
- `npm run lint`: Run ESLint
- `npm run clean`: Remove build directory

## Project Structure

```
src/
  ├── index.ts        # Main application entry point
  └── routes/
      └── health.ts   # Example health check route
```
