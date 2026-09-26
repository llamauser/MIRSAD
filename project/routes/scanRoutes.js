const express = require('express');
const router = express.Router();
const ScanController = require('../controllers/scanController');

// Process barcode scan (inbound/outbound)
router.post('/', ScanController.processScan);

// Get scan history/activity
router.get('/history', ScanController.getScanHistory);

module.exports = router;
