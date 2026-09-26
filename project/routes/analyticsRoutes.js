const express = require('express');
const router = express.Router();
const db = require('../database/inMemoryDB');

router.get('/warehouse', async (req, res) => {
  try {
    const products = db.getAllProducts();
    const stats = db.getStats();
    
    res.json({
      summary: stats,
      velocity: {
        A: products.filter(p => p.velocityClass === 'A').length,
        B: products.filter(p => p.velocityClass === 'B').length,
        C: products.filter(p => p.velocityClass === 'C').length
      },
      stockLevels: {
        low: products.filter(p => db.isLowStock(p)).length,
        adequate: products.filter(p => !db.isLowStock(p) && p.quantity < p.maxStock * 0.8).length,
        high: products.filter(p => p.quantity >= p.maxStock * 0.8).length
      }
    });
  } catch (error) {
    console.error('Error fetching analytics:', error);
    res.status(500).json({ error: 'Failed to fetch analytics', details: error.message });
  }
});

router.get('/top-products', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 10;
    const products = db.getAllProducts().sort((a, b) => b.demandScore - a.demandScore).slice(0, limit);

    const topProducts = products.map(p => ({
      barcode: p.barcode,
      sku: p.sku,
      name: p.name,
      velocityClass: p.velocityClass,
      demandScore: Math.round(p.demandScore * 10) / 10,
      turnoverRate: Math.round((p.turnoverRate || 0) * 10) / 10,
      quantity: p.quantity,
      location: db.getFullLocation(p.storageLocation)
    }));

    res.json({ topProducts });
  } catch (error) {
    console.error('Error fetching top products:', error);
    res.status(500).json({ error: 'Failed to fetch top products', details: error.message });
  }
});

module.exports = router;
