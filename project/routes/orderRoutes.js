const express = require('express');
const router = express.Router();
const OrderController = require('../controllers/orderController');

// Get all orders (with optional filters)
router.get('/', OrderController.getAllOrders);

// Get single order
router.get('/:id', OrderController.getOrder);

// Create new order
router.post('/', OrderController.createOrder);

// Update order status
router.patch('/:id/status', OrderController.updateOrderStatus);

// Mark item as picked
router.patch('/:id/items/:itemId/picked', OrderController.markItemPicked);

// Delete order
router.delete('/:id', OrderController.deleteOrder);

module.exports = router;
