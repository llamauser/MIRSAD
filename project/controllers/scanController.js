const db = require('../database/inMemoryDB');

class ScanController {
  /**
   * Process barcode scan for inbound/outbound operations
   */
  static async processScan(req, res) {
    try {
      const { barcode, type, quantity } = req.body;

      if (!barcode || !type || !quantity) {
        return res.status(400).json({ 
          error: 'Missing required fields: barcode, type, quantity' 
        });
      }

      if (!['IN', 'OUT'].includes(type)) {
        return res.status(400).json({ 
          error: 'Type must be either IN or OUT'
        });
      }

      const result = db.processScan(barcode, type, quantity);

      if (result.error) {
        return res.status(400).json({ error: result.error });
      }

      const product = result.product;

      // Broadcast to WebSocket clients
      if (global.broadcast) {
        global.broadcast({
          type: type === 'IN' ? 'WAREHOUSE_INBOUND' : 'WAREHOUSE_OUTBOUND',
          product: {
            barcode: product.barcode,
            sku: product.sku,
            name: product.name,
            quantity: product.quantity,
            location: db.getFullLocation(product.storageLocation),
            lowStock: db.isLowStock(product)
          },
          scanned: parseInt(quantity)
        });
      }

      return res.json({
        success: true,
        message: `${type === 'IN' ? 'Inbound' : 'Outbound'}: ${type === 'IN' ? 'Added' : 'Removed'} ${quantity} units`,
        product: {
          barcode: product.barcode,
          sku: product.sku,
          name: product.name,
          quantity: product.quantity,
          location: db.getFullLocation(product.storageLocation),
          velocityClass: product.velocityClass,
          lowStock: db.isLowStock(product),
          demandScore: Math.round(product.demandScore * 10) / 10
        }
      });

    } catch (error) {
      console.error('Scan processing error:', error);
      res.status(500).json({ 
        error: 'Failed to process scan',
        details: error.message 
      });
    }
  }

  /**
   * Get scan history/activity
   */
  static async getScanHistory(req, res) {
    try {
      const limit = parseInt(req.query.limit) || 50;
      const activity = db.getScanHistory(limit);

      res.json({ activity });

    } catch (error) {
      console.error('Error fetching scan history:', error);
      res.status(500).json({ 
        error: 'Failed to fetch scan history',
        details: error.message 
      });
    }
  }
}

module.exports = ScanController;
