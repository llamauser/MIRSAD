const Product = require('../models/Product');
const DemandEngine = require('../services/demandEngine');
const SlottingEngine = require('../services/slottingEngine');

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

      // Find product by barcode
      let product = await Product.findOne({ barcode });

      if (!product && type === 'OUT') {
        return res.status(404).json({ 
          error: 'Product not found. Cannot process outbound scan.' 
        });
      }

      // Handle INBOUND scan
      if (type === 'IN') {
        if (!product) {
          return res.status(404).json({ 
            error: 'Product not found. Please add product first.' 
          });
        }

        // Update quantity
        product.quantity += parseInt(quantity);
        
        // Add movement record
        product.movementHistory.push({
          type: 'IN',
          quantity: parseInt(quantity),
          toLocation: product.getFullLocation(),
          timestamp: new Date()
        });
        
        product.lastMovement = new Date();
        await product.save();

        // Broadcast to WebSocket clients
        if (global.broadcast) {
          global.broadcast({
            type: 'WAREHOUSE_INBOUND',
            product: {
              barcode: product.barcode,
              sku: product.sku,
              name: product.name,
              quantity: product.quantity,
              location: product.getFullLocation()
            },
            scanned: parseInt(quantity)
          });
        }

        return res.json({
          success: true,
          message: `Inbound: Added ${quantity} units`,
          product: {
            barcode: product.barcode,
            sku: product.sku,
            name: product.name,
            quantity: product.quantity,
            location: product.getFullLocation(),
            velocityClass: product.velocityClass
          }
        });
      }

      // Handle OUTBOUND scan
      if (type === 'OUT') {
        if (product.quantity < parseInt(quantity)) {
          return res.status(400).json({ 
            error: `Insufficient stock. Available: ${product.quantity}, Requested: ${quantity}` 
          });
        }

        // Update quantity
        product.quantity -= parseInt(quantity);
        
        // Add movement record
        product.movementHistory.push({
          type: 'OUT',
          quantity: parseInt(quantity),
          fromLocation: product.getFullLocation(),
          timestamp: new Date()
        });
        
        product.lastMovement = new Date();
        
        // Update demand metrics
        const metrics = DemandEngine.updateProductMetrics(product);
        product.demandScore = metrics.demandScore;
        product.turnoverRate = metrics.turnoverRate;
        
        await product.save();

        // Recalculate velocity class for all products
        const allProducts = await Product.find({});
        const velocityMap = DemandEngine.classifyVelocity(allProducts);
        
        // Update this product's velocity class
        const newVelocityClass = velocityMap.get(product._id.toString());
        if (newVelocityClass && newVelocityClass !== product.velocityClass) {
          product.velocityClass = newVelocityClass;
          await product.save();
        }

        // Broadcast to WebSocket clients
        if (global.broadcast) {
          global.broadcast({
            type: 'WAREHOUSE_OUTBOUND',
            product: {
              barcode: product.barcode,
              sku: product.sku,
              name: product.name,
              quantity: product.quantity,
              location: product.getFullLocation(),
              lowStock: product.isLowStock()
            },
            scanned: parseInt(quantity)
          });
        }

        return res.json({
          success: true,
          message: `Outbound: Removed ${quantity} units`,
          product: {
            barcode: product.barcode,
            sku: product.sku,
            name: product.name,
            quantity: product.quantity,
            location: product.getFullLocation(),
            velocityClass: product.velocityClass,
            lowStock: product.isLowStock(),
            demandScore: Math.round(product.demandScore * 10) / 10
          }
        });
      }

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
      
      // Get all products with recent movements
      const products = await Product.find({ 
        lastMovement: { $exists: true } 
      })
        .sort({ lastMovement: -1 })
        .limit(limit);

      const activity = [];
      
      products.forEach(product => {
        // Get last movement
        const lastMovement = product.movementHistory[product.movementHistory.length - 1];
        if (lastMovement) {
          activity.push({
            timestamp: lastMovement.timestamp,
            type: lastMovement.type,
            barcode: product.barcode,
            sku: product.sku,
            name: product.name,
            quantity: lastMovement.quantity,
            location: product.getFullLocation()
          });
        }
      });

      // Sort by timestamp descending
      activity.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

      res.json({ activity: activity.slice(0, limit) });

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
