import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import healthRouter from './routes/health';

dotenv.config();

const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.use('/api/health', healthRouter);

// Root route
app.get('/', (req, res) => {
  res.status(200).json({
    message: 'Node.js Express TypeScript Boilerplate is running!'
  });
});

// Error handling middleware
app.use((req, res) => {
  res.status(404).json({
    error: 'Not Found'
  });
});

// Start server
const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
