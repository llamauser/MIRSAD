const express = require('express');
const router = express.Router();
const ProductController = require('../controllers/productController');

// Get all products (with optional filters)
router.get('/', ProductController.getAllProducts);

// Get dashboard statistics
router.get('/stats', ProductController.getDashboardStats);

// Optimize warehouse slotting
router.post('/optimize', ProductController.optimizeSlotting);

// Get single product
router.get('/:id', ProductController.getProduct);

// Create product
router.post('/', ProductController.createProduct);

// Update product
router.put('/:id', ProductController.updateProduct);

// Delete product
router.delete('/:id', ProductController.deleteProduct);

module.exports = router;
