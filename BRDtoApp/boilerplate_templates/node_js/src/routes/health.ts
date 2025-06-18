import { Router } from 'express';

const router = Router();

router.get('/', (_, res) => {
  res.status(200).json({
    status: 'OK',
    timestamp: new Date().toISOString()
  });
});

export default router;
