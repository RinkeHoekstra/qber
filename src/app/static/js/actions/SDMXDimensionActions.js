var QBerDispatcher = require('../dispatcher/QBerDispatcher');
var QBerAPI = require('../utils/QBerAPI');
var SDMXDimensionConstants = require('../constants/SDMXDimensionConstants');
var DatasetConstants = require('../constants/DatasetConstants');
var MessageConstants = require('../constants/MessageConstants');

/**
 *  Note that the QBerAPI also dispatches actions to stores!
 */
var SDMXDimensionActions = {

  /**
   * @param {string} search
   */
  searchDimension: function(search) {
    console.log("In searchDimension action: "+search);
    QBerDispatcher.dispatch({
      actionType: SDMXDimensionConstants.SDMX_DIMENSION_SEARCH,
      search: search
    });
  },

  /**
   * @param {string} search
   */
  selectDimension: function(dimension) {
    QBerDispatcher.dispatch({
      actionType: MessageConstants.INFO,
      message: 'You selected dimension '+dimension
    });
    console.log("In searchDimension action");
    QBerDispatcher.dispatch({
      actionType: SDMXDimensionConstants.SELECT_DIMENSION,
      dimension: dimension
    });
    QBerDispatcher.dispatch({
      actionType: DatasetConstants.DATASET_CHOOSE_DIMENSION,
      dimension: dimension
    });
  }
};

module.exports = SDMXDimensionActions;