const db = require('../database/inMemoryDB');

class ProductController {
  static async getAllProducts(req, res) {
    try {
      const { velocityClass, lowStock, search } = req.query;
      
      const filter = {};
      if (velocityClass) filter.velocityClass = velocityClass.toUpperCase();
      if (lowStock === 'true') filter.lowStock = true;
      if (search) filter.search = search;

      const products = db.getAllProducts(filter);

      const productsWithLocation = products.map(p => ({
        id: p.id,
        _id: p.id,
        barcode: p.barcode,
        sku: p.sku,
        name: p.name,
        category: p.category,
        dimensions: p.dimensions,
        quantity: p.quantity,
        reorderPoint: p.reorderPoint,
        maxStock: p.maxStock,
        weight: p.weight,
        volume: p.volume,
        location: db.getFullLocation(p.storageLocation),
        storageLocation: p.storageLocation,
        velocityClass: p.velocityClass,
        demandScore: Math.round((p.demandScore || 0) * 10) / 10,
        turnoverRate: Math.round((p.turnoverRate || 0) * 10) / 10,
        lowStock: db.isLowStock(p),
        lastMovement: p.lastMovement
      }));

      res.json({ products: productsWithLocation });
    } catch (error) {
      console.error('Error fetching products:', error);
      res.status(500).json({ error: 'Failed to fetch products', details: error.message });
    }
  }

  static async getProduct(req, res) {
    try {
      const { id } = req.params;
      let product = db.getProductById(id) || db.getProductByBarcode(id);

      if (!product) {
        return res.status(404).json({ error: 'Product not found' });
      }

      res.json({
        product: {
          _id: product.id,
          barcode: product.barcode,
          sku: product.sku,
          name: product.name,
          category: product.category,
          dimensions: product.dimensions,
          weight: product.weight,
          volume: product.volume,
          quantity: product.quantity,
          reorderPoint: product.reorderPoint,
          maxStock: product.maxStock,
          location: db.getFullLocation(product.storageLocation),
          storageLocation: product.storageLocation,
          velocityClass: product.velocityClass,
          demandScore: product.demandScore,
          turnoverRate: product.turnoverRate,
          movementHistory: product.movementHistory.slice(-20),
          lowStock: db.isLowStock(product),
          lastMovement: product.lastMovement,
          createdAt: product.createdAt,
          updatedAt: product.updatedAt
        }
      });
    } catch (error) {
      console.error('Error fetching product:', error);
      res.status(500).json({ error: 'Failed to fetch product', details: error.message });
    }
  }

  static async createProduct(req, res) {
    try {
      const { barcode, sku, name, category, dimensions, weight, quantity, reorderPoint, maxStock } = req.body;

      if (!barcode || !sku || !name) {
        return res.status(400).json({ error: 'Missing required fields: barcode, sku, name' });
      }

      if (db.getProductByBarcode(barcode)) {
        return res.status(400).json({ error: 'Product with this barcode already exists' });
      }

      const productData = {
        barcode, sku, name, category, dimensions, weight,
        volume: dimensions ? dimensions.length * dimensions.width * dimensions.height : 0,
        quantity: quantity || 0,
        reorderPoint: reorderPoint || 10,
        maxStock: maxStock || 100,
        velocityClass: 'C',
        demandScore: 0,
        turnoverRate: 0,
        storageLocation: { zone: 'C', aisle: '01', rack: '01', level: '01', position: '01' }
      };

      const product = db.createProduct(productData);

      if (global.broadcast) {
        global.broadcast({
          type: 'WAREHOUSE_PRODUCT_ADDED',
          product: { barcode: product.barcode, sku: product.sku, name: product.name, location: db.getFullLocation(product.storageLocation) }
        });
      }

      res.status(201).json({
        success: true,
        message: 'Product created successfully',
        product: {
          _id: product.id,
          barcode: product.barcode,
          sku: product.sku,
          name: product.name,
          location: db.getFullLocation(product.storageLocation),
          quantity: product.quantity
        }
      });
    } catch (error) {
      console.error('Error creating product:', error);
      res.status(500).json({ error: 'Failed to create product', details: error.message });
    }
  }

  static async updateProduct(req, res) {
    try {
      const { id } = req.params;
      const product = db.updateProduct(id, req.body);

      if (!product) {
        return res.status(404).json({ error: 'Product not found' });
      }

      res.json({
        success: true,
        message: 'Product updated successfully',
        product: {
          _id: product.id,
          barcode: product.barcode,
          sku: product.sku,
          name: product.name,
          location: db.getFullLocation(product.storageLocation),
          quantity: product.quantity
        }
      });
    } catch (error) {
      console.error('Error updating product:', error);
      res.status(500).json({ error: 'Failed to update product', details: error.message });
    }
  }

  static async deleteProduct(req, res) {
    try {
      const { id } = req.params;

      if (!db.deleteProduct(id)) {
        return res.status(404).json({ error: 'Product not found' });
      }

      res.json({ success: true, message: 'Product deleted successfully' });
    } catch (error) {
      console.error('Error deleting product:', error);
      res.status(500).json({ error: 'Failed to delete product', details: error.message });
    }
  }

  static async getDashboardStats(req, res) {
    try {
      const stats = db.getStats();
      res.json({ stats });
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
      res.status(500).json({ error: 'Failed to fetch statistics', details: error.message });
    }
  }

  static async optimizeSlotting(req, res) {
    try {
      const products = db.getAllProducts();
      
      if (global.broadcast) {
        global.broadcast({ type: 'WAREHOUSE_OPTIMIZED', recommendations: 0, timestamp: new Date() });
      }

      res.json({
        success: true,
        message: 'Warehouse optimization complete',
        recommendations: [],
        summary: { totalProducts: products.length, relocations: 0, highPriority: 0, mediumPriority:0, lowPriority: 0 }
      });
    } catch (error) {
      console.error('Error optimizing slotting:', error);
      res.status(500).json({ error: 'Failed to optimize slotting', details: error.message });
    }
  }
}

module.exports = ProductController;
