# By Nick Erickson, Benjamin Hillmann, Sivaraman Rajaganapathy
# Contains main functions for detecting a game loss

import numpy as np

meanLight = 0
meanDiff = 0
maxDiff = 0
maxMean = 0
prevMean = 0
c = 0

# Resets globals
def reset_globs():
    global prevMean, meanDiff, meanLight, c, maxDiff, maxMean
    prevMean = 0
    meanDiff = 0 # Currently unused
    meanLight = 0
    maxDiff = 0 # Current unused
    maxMean = 0
    prevMean = 0
    c = 0
    

#==============================================================================
# 
#==============================================================================
def colourTermination(img):
    if np.sum(np.abs(img[:,:,0]-img[:,:,1]) + np.abs(img[:, :, 0]-img[:,:,2]) + np.abs(img[:, :, 1]-img[:, :, 2])) > 0:
        return(True)
    return(False)
#==============================================================================    
    
    
# Gets the optimal move
def get_move(data, moves):
    global prevMean, meanDiff, meanLight, c, maxDiff, maxMean
    c += 1
    
    ##############################################################
    # Check if you lost, screen goes white when you lose, so check
    curMean = np.mean(data)
    if c <= 60:
        maxDiff = 0
        meanLight += curMean
        if c == 60:
            meanLight = meanLight / 60
    else:
        meanLight = meanLight * (9/10) + curMean * (1/10)
        diff = curMean - prevMean
        meanDiff = (meanDiff*((c-1)/c) + abs(diff)*(1/c))
        maxDiff = max(maxDiff, abs(diff))
        maxMean = max(curMean, maxMean)
        #print(meanDiff, diff)
        threshold = (160 - meanLight) / 2
        #print(threshold, diff, maxDiff)
        #print(diff, threshold)

        if diff > threshold:
            return 'esc' # Lost!
    prevMean = curMean
    
    ##############################################################
    # Compute the optimal move
    optimal_move = moves[np.random.randint(0,3)]
    ##############################################################
    
    return optimal_move
    
    
    