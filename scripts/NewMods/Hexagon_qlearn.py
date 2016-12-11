#!/usr/bin/env python
from __future__ import print_function

import globs as G
import argparse
import skimage as skimage
from skimage import transform, color, exposure
from skimage.transform import rotate
from skimage.viewer import ImageViewer
import scipy.misc as smp
import sys
#sys.path.append("game/")
#import wrapped_flappy_bird as game
import random
import numpy as np
import time
from collections import deque

import json
from keras import initializations
from keras.initializations import normal, identity
from keras.models import model_from_json
from keras.models import Sequential
from keras.layers.core import Dense, Dropout, Activation, Flatten
from keras.layers.convolutional import Convolution2D, MaxPooling2D
from keras.optimizers import SGD , Adam
#%%
import importlib
import OpenHexagonEmulator
import terminal_detection
#importlib.reload(OpenHexagonEmulator)
from OpenHexagonEmulator import gameState
keys = np.array(['none', 'left_arrow', 'right_arrow'])

from ToPolar import img2polar

#%%
GAME = 'bird' # the name of the game being played for log files
CONFIG = 'nothreshold'
ACTIONS = 3 # number of valid actions
GAMMA = 0.99 # decay rate of past observations
OBSERVATION = 3200. # timesteps to observe before training
EXPLORE = 3000000. # frames over which to anneal epsilon
FINAL_EPSILON = 0.0001 # final value of epsilon
INITIAL_EPSILON = 0.1 # starting value of epsilon
REPLAY_MEMORY = 50000 # number of previous transitions to remember
BATCH = 128 #32 # size of minibatch
FRAME_PER_ACTION = 1

#OpenHexagonEmulator.configure()

img_rows , img_cols = G.x_size_final, G.y_size_final

print('Resolution: ', img_rows, img_cols)
#Convert image into Black and white
img_channels = 2 #We stack 4 frames




#==============================================================================
# CNN model structure (Unmodified)
#==============================================================================
def buildmodel():
    print("Now we build the model")
    model = Sequential()
    model.add(Convolution2D(32, 8, 8, subsample=(4,4),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same',input_shape=(img_channels,img_rows,img_cols)))
    model.add(Activation('relu'))
    model.add(Convolution2D(64, 4, 4, subsample=(2,2),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same'))
    model.add(Activation('relu'))
    model.add(Convolution2D(64, 3, 3, subsample=(1,1),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same'))
    model.add(Activation('relu'))
    model.add(Flatten())
    model.add(Dense(512, init=lambda shape, name: normal(shape, scale=0.01, name=name)))
    model.add(Activation('relu'))
    model.add(Dense(ACTIONS,init=lambda shape, name: normal(shape, scale=0.01, name=name)))
   
    adam = Adam(lr=1e-6)
    model.compile(loss='mse',optimizer=adam)
    print("We finish building the model")
    
    #print(model.layers)
    return model
#==============================================================================

def prepareImage(image):
    tmpImage = skimage.color.rgb2gray(image)
    #thresh = skimage.filters.threshold_otsu(tmpImage)
    #print('image shape')
    #print(np.shape(tmpImage))      
    tmpImage = img2polar(tmpImage, [100,100], 100, 0, 100) 
    #tmpImage = tmpImage > thresh
    tmpImage = skimage.transform.resize(tmpImage,(img_rows , img_cols))
    #img = smp.toimage(tmpImage) 

    
    #img.show()
    #print('image shape')
    #print(np.shape(tmpImage))            
    
    #tmpImage = skimage.exposure.rescale_intensity(tmpImage, out_range=(0, 255))
    
    #print(tmpImage)
    #img = smp.toimage(binary)
    #img.show()
    #smp.imsave('outfile.png', img)
    #exit(1)
    #time.sleep(5)
    #print(tmpImage.shape)
    tmpImage = tmpImage.reshape(1, 1, tmpImage.shape[0], tmpImage.shape[1])
    
    return tmpImage

#==============================================================================
# CNN model based Q-learning - adapted for openhexagon
#==============================================================================
def trainNetwork(model,args):
    # open up a game state to communicate with emulator
    #game_state = game.GameState()
    

    # store the previous observations in replay memory
    D = deque()
    Dtemp = deque()
    # get the first state by doing nothing and preprocess the image to 80x80x4
    do_nothing = np.zeros(ACTIONS)
    do_nothing[0] = 1
    x_t, r_0, terminal = gameState('enter')#game_state.frame_step(do_nothing)
    #print(x_t.shape)
    x_t = prepareImage(x_t)
    #print(x_t.shape)
    s_t = np.stack((x_t, x_t), axis=0)
    print(s_t.shape)
    #In Keras, need to reshape
    print(s_t.shape)
    s_t = s_t.reshape(1, s_t.shape[0], s_t.shape[3], s_t.shape[4])
    print(s_t.shape)
    print(s_t.shape)
    if args['mode'] == 'Run':
        OBSERVE = 999999999    #We keep observe, never trai
        epsilon = FINAL_EPSILON
        print ("Now we load weight")
        model.load_weights("model.h5")
        adam = Adam(lr=1e-6)
        model.compile(loss='mse',optimizer=adam)
        print ("Weight load successfully")
    elif args['mode'] == 'Train_old': # Continue training old network
        OBSERVE = OBSERVATION
        epsilon = INITIAL_EPSILON
        print ("Now we load weight")
        model.load_weights("model.h5")
        adam = Adam(lr=1e-6)
        model.compile(loss='mse',optimizer=adam)
        print ("Weight load successfully")
    else:                       #We go to training mode
        print('Training new network!')
        OBSERVE = OBSERVATION
        epsilon = INITIAL_EPSILON

    t = 0
    run_count = -1
    saveIterator = 0
    saveThreshold = 10000
    framerate = 30 # Temp
    survival_times = []
    while (True):
        run_count += 1
        run_start_t = t
        alive = True
        OpenHexagonEmulator.press('enter')
        time.sleep(0.1)
        OpenHexagonEmulator.release('enter')
        start_time = time.time()
        current_run_frames = 0
        useRate = np.zeros([ACTIONS])
        while alive == True:
            #print(s_t.shape)
            action_index = 0
            r_t = 0
            a_t = np.zeros([ACTIONS])
            #choose an action epsilon greedy
            if t % FRAME_PER_ACTION == 0:
                if random.random() <= epsilon:
                    #print("----------Random Action----------")
                    action_index = random.randrange(ACTIONS)
                else:
                    q = model.predict(s_t)       #input a stack of 4 images, get the prediction
                    action_index = np.argmax(q)
                    
                a_t[action_index] = 1
                
            #We reduced the epsilon gradually
            if epsilon > FINAL_EPSILON and t > OBSERVE:
                epsilon -= (INITIAL_EPSILON - FINAL_EPSILON) / EXPLORE
    
            #run the selected action and observed next state and reward        
            x_t1_colored, r_t, terminal = gameState(keys[action_index])
            
            x_t1 = prepareImage(x_t1_colored)
            
            s_t1 = np.append(x_t1, s_t[:, :img_channels-1, :, :], axis=1)

            
            # store the transition in Dtemo
            if current_run_frames > framerate*0: # Don't store early useless frames
                Dtemp.append([s_t, action_index, r_t, s_t1, terminal])
                if len(Dtemp) > REPLAY_MEMORY:
                    Dtemp.popleft()
            else:
                useRate = useRate + a_t            
            
            '''    
            # store the transition in D
            if current_run_frames > framerate*2: # Don't store early useless frames
                D.append((s_t, action_index, r_t, s_t1, terminal))
                if len(D) > REPLAY_MEMORY:
                    D.popleft()
            else:
                useRate = useRate + a_t                
            #elif current_run_frames > framerate*4 - 1:
                #print('hi')
            '''
            
    
            s_t = s_t1
            t = t + 1
            current_run_frames += 1
            saveIterator += 1
    
            
    
            # print info
            state = ""
            if t <= OBSERVE:
                state = "observe"
            elif t > OBSERVE and t <= OBSERVE + EXPLORE:
                state = "explore"
            else:
                state = "train"
            if t % 1000 == 0:
                print("TS", t, "/ S", state, \
                    "/ E %.2f" % epsilon + " / A", action_index, "/ R", r_t)
            
            if terminal == 1:
                # Lost!
                alive = 0
                
            if current_run_frames > 50000:
                # Likely stuck, just go to new level
                print('Stuck! Moving on...')
                alive = 0
                
        for lclCnt in range(1,min(np.size(Dtemp,0),200),1):
            if lclCnt <=10:
                Dtemp[-lclCnt][2] = -0.1
            D.append(Dtemp[-lclCnt]) 
        Dtemp.clear()               
        
        end_time = time.time()
        OpenHexagonEmulator.release(G.curKey)
        time.sleep(0.1)
        OpenHexagonEmulator.press('esc')
        time.sleep(0.1)
        OpenHexagonEmulator.release('esc')
        terminal_detection.reset_globs()
        
        useRate = useRate/np.sum(useRate)
        survival_time = end_time - start_time
        framerate = (t - run_start_t)/survival_time
        survival_times.append(survival_time)
        print('Run ' + str(run_count) + ' survived ' + "%.2f" % survival_time + 's' + ', %.2f fps' % framerate + ', key: ', ['%.2f' % k for k in useRate])
        print('Mean: %.2f' % np.mean(survival_times), 'Max: %.2f' % np.max(survival_times), 'Last 100: %.2f' % np.mean(survival_times[-100:]))
        print(epsilon)
        print('\n')
        # Now Train!
        #only train if done observing
        if t > OBSERVE:
            loss = 0
            Q_sa = 0
            #sample a minibatch to train on
            minibatch = random.sample(D, BATCH)

            inputs = np.zeros((BATCH, s_t.shape[1], s_t.shape[2], s_t.shape[3]))   #32, 80, 80, 4
            targets = np.zeros((inputs.shape[0], ACTIONS))                         #32, 2

            #Now we do the experience replay
            for i in range(0, len(minibatch)):
                state_t = minibatch[i][0]
                action_t = minibatch[i][1]   #This is action index
                reward_t = minibatch[i][2]
                state_t1 = minibatch[i][3]
                terminal = minibatch[i][4]
                # if terminated, only equals reward

                inputs[i:i + 1] = state_t    #I saved down s_t

                targets[i] = model.predict(state_t)  # Hitting each button probability
                Q_sa = model.predict(state_t1)

                if terminal:
                    targets[i, action_t] = reward_t
                else:
                    targets[i, action_t] = reward_t + GAMMA * np.max(Q_sa)

            # targets2 = normalize(targets)
            loss += model.train_on_batch(inputs, targets)        
        
            if saveIterator >= saveThreshold:
                saveIterator = 0
                # save progress every 10000 iterations
                print("Saving Model...")
                model.save_weights("model.h5", overwrite=True)
                with open("model.json", "w") as outfile:
                    json.dump(model.to_json(), outfile)
        
            print("Q_MAX " , np.max(Q_sa), "/ L ", loss)
        # Prep for next round
        time.sleep(0.2)
            
    print("Episode finished!")
    print("************************")
#==============================================================================

#==============================================================================
# Unmodified
#==============================================================================
def playGame(args):
    model = buildmodel()
    trainNetwork(model,args)
#==============================================================================
    

#==============================================================================
# Modified to run from Spyder Command window
#==============================================================================
def main():    
    #parser = argparse.ArgumentParser(description='Description of your program')
    #parser.add_argument('-m','--mode', help='Train / Run', required=True)    
    #args = vars(parser.parse_args())
    
    args = {'mode' : 'Train'}
    #args = {'mode' : 'Run'}
    playGame(args)    
#==============================================================================


#==============================================================================
# Unmodified
#==============================================================================
if __name__ == "__main__":
    main() 
#==============================================================================
