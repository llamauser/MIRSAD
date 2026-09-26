/**
 * In-Memory Database - Hardcoded warehouse data
 * No MongoDB required
 */

class InMemoryDB {
  constructor() {
    this.products = new Map();
    this.orders = new Map();
    this.scanHistory = [];
    this.orderCounter = 1;
    
    // Initialize with sample products
    this.initializeSampleData();
  }

  initializeSampleData() {
    const sampleProducts = [
      {
        id: '1',
        barcode: '8901234567890',
        sku: 'FRIDGE-001',
        name: 'Samsung Double Door Refrigerator',
        category: 'Appliances',
        dimensions: { length: 70, width: 75, height: 180 },
        weight: 85,
        volume: 945000,
        quantity: 15,
        reorderPoint: 5,
        maxStock: 30,
        velocityClass: 'A',
        demandScore: 25.5,
        turnoverRate: 3.2,
        storageLocation: { zone: 'A', aisle: '01', rack: '01', level: '01', position: '01' },
        movementHistory: [],
        lastMovement: new Date(),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        id: '2',
        barcode: '8901234567891',
        sku: 'TV-001',
        name: 'LG 55" 4K Smart TV',
        category: 'Electronics',
        dimensions: { length: 125, width: 10, height: 75 },
        weight: 18,
        volume: 93750,
        quantity: 25,
        reorderPoint: 8,
        maxStock: 50,
        velocityClass: 'A',
        demandScore: 32.8,
        turnoverRate: 4.5,
        storageLocation: { zone: 'A', aisle: '01', rack: '02', level: '02', position: '01' },
        movementHistory: [],
        lastMovement: new Date(),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        id: '3',
        barcode: '8901234567892',
        sku: 'WASH-001',
        name: 'Whirlpool Washing Machine',
        category: 'Appliances',
        dimensions: { length: 60, width: 65, height: 90 },
        weight: 65,
        volume: 351000,
        quantity: 12,
        reorderPoint: 4,
        maxStock: 25,
        velocityClass: 'B',
        demandScore: 18.3,
        turnoverRate: 2.1,
        storageLocation: { zone: 'B', aisle: '02', rack: '01', level: '01', position: '01' },
        movementHistory: [],
        lastMovement: new Date(),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        id: '4',
        barcode: '8901234567893',
        sku: 'AC-001',
        name: 'Daikin Split AC 1.5 Ton',
        category: 'Appliances',
        dimensions: { length: 90, width: 30, height: 25 },
        weight: 12,
        volume: 67500,
        quantity: 20,
        reorderPoint: 6,
        maxStock: 40,
        velocityClass: 'B',
        demandScore: 15.7,
        turnoverRate: 2.8,
        storageLocation: { zone: 'B', aisle: '02', rack: '02', level: '02', position: '01' },
        movementHistory: [],
        lastMovement: new Date(),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        id: '5',
        barcode: '8901234567894',
        sku: 'MW-001',
        name: 'Panasonic Microwave Oven',
        category: 'Kitchen',
        dimensions: { length: 50, width: 40, height: 30 },
        weight: 15,
        volume: 60000,
        quantity: 30,
        reorderPoint: 10,
        maxStock: 60,
        velocityClass: 'A',
        demandScore: 28.4,
        turnoverRate: 3.9,
        storageLocation: { zone: 'A', aisle: '01', rack: '03', level: '03', position: '01' },
        movementHistory: [],
        lastMovement: new Date(),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        id: '6',
        barcode: '8901234567895',
        sku: 'FAN-001',
        name: 'Havells Ceiling Fan',
        category: 'Electronics',
        dimensions: { length: 60, width: 60, height: 20 },
        weight: 5,
        volume: 72000,
        quantity: 45,
        reorderPoint: 15,
        maxStock: 80,
        velocityClass: 'C',
        demandScore: 8.2,
        turnoverRate: 1.3,
        storageLocation: { zone: 'C', aisle: '03', rack: '01', level: '03', position: '01' },
        movementHistory: [],
        lastMovement: new Date(),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        id: '7',
        barcode: '8901234567896',
        sku: 'IRON-001',
        name: 'Philips Steam Iron',
        category: 'Kitchen',
        dimensions: { length: 30, width: 15, height: 15 },
        weight: 2,
        volume: 6750,
        quantity: 50,
        reorderPoint: 20,
        maxStock: 100,
        velocityClass: 'C',
        demandScore: 6.5,
        turnoverRate: 1.1,
        storageLocation: { zone: 'C', aisle: '03', rack: '02', level: '03', position: '02' },
        movementHistory: [],
        lastMovement: new Date(),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        id: '8',
        barcode: '8901234567897',
        sku: 'OVEN-001',
        name: 'Samsung Convection Oven',
        category: 'Kitchen',
        dimensions: { length: 55, width: 50, height: 35 },
        weight: 22,
        volume: 96250,
        quantity: 8,
        reorderPoint: 3,
        maxStock: 15,
        velocityClass: 'B',
        demandScore: 12.1,
        turnoverRate: 1.8,
        storageLocation: { zone: 'B', aisle: '02', rack: '03', level: '02', position: '01' },
        movementHistory: [],
        lastMovement: new Date(),
        createdAt: new Date(),
        updatedAt: new Date()
      }
    ];

    sampleProducts.forEach(product => {
      this.products.set(product.id, product);
    });

    console.log(`✓ Initialized ${this.products.size} sample products`);
  }

  // Product methods
  getAllProducts(filter = {}) {
    let products = Array.from(this.products.values());

    if (filter.velocityClass) {
      products = products.filter(p => p.velocityClass === filter.velocityClass);
    }

    if (filter.lowStock) {
      products = products.filter(p => p.quantity <= p.reorderPoint);
    }

    if (filter.search) {
      const search = filter.search.toLowerCase();
      products = products.filter(p =>
        p.name.toLowerCase().includes(search) ||
        p.sku.toLowerCase().includes(search) ||
        p.barcode.includes(search)
      );
    }

    return products;
  }

  getProductById(id) {
    return this.products.get(id);
  }

  getProductByBarcode(barcode) {
    return Array.from(this.products.values()).find(p => p.barcode === barcode);
  }

  createProduct(productData) {
    const id = String(this.products.size + 1);
    const product = {
      id,
      ...productData,
      movementHistory: [],
      createdAt: new Date(),
      updatedAt: new Date()
    };
    this.products.set(id, product);
    return product;
  }

  updateProduct(id, updates) {
    const product = this.products.get(id);
    if (!product) return null;

    Object.assign(product, updates, { updatedAt: new Date() });
    this.products.set(id, product);
    return product;
  }

  deleteProduct(id) {
    return this.products.delete(id);
  }

  // Scan methods
  processScan(barcode, type, quantity) {
    const product = this.getProductByBarcode(barcode);
    if (!product) return { error: 'Product not found' };

    const movement = {
      timestamp: new Date(),
      type,
      quantity: parseInt(quantity),
      fromLocation: type === 'OUT' ? this.getFullLocation(product.storageLocation) : null,
      toLocation: type === 'IN' ? this.getFullLocation(product.storageLocation) : null
    };

    product.movementHistory.push(movement);
    product.lastMovement = new Date();

    if (type === 'IN') {
      product.quantity += parseInt(quantity);
    } else if (type === 'OUT') {
      if (product.quantity < parseInt(quantity)) {
        return { error: 'Insufficient stock' };
      }
      product.quantity -= parseInt(quantity);
    }

    this.scanHistory.unshift({
      ...movement,
      barcode: product.barcode,
      sku: product.sku,
      name: product.name,
      location: this.getFullLocation(product.storageLocation)
    });

    // Keep only last 100 scan records
    if (this.scanHistory.length > 100) {
      this.scanHistory = this.scanHistory.slice(0, 100);
    }

    return { success: true, product };
  }

  getScanHistory(limit = 50) {
    return this.scanHistory.slice(0, limit);
  }

  // Statistics
  getStats() {
    const products = Array.from(this.products.values());
    return {
      totalProducts: products.length,
      lowStockAlerts: products.filter(p => p.quantity <= p.reorderPoint).length,
      highVelocityItems: products.filter(p => p.velocityClass === 'A').length,
      totalInventoryUnits: products.reduce((sum, p) => sum + p.quantity, 0),
      pendingOrders: this.orders.size
    };
  }

  // Helper methods
  getFullLocation(storageLocation) {
    if (!storageLocation || !storageLocation.zone) return 'UNASSIGNED';
    const loc = storageLocation;
    return `${loc.zone}-${loc.aisle}-${loc.rack}-${loc.level}-${loc.position}`;
  }

  isLowStock(product) {
    return product.quantity <= product.reorderPoint;
  }
}

// Export singleton instance
module.exports = new InMemoryDB();
