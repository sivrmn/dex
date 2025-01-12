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
import graphHelper
#importlib.reload(OpenHexagonEmulator)
from OpenHexagonEmulator import gameState
keys = np.array(['none', 'left_arrow', 'right_arrow'])

t = 0

#%%
GAME = 'bird' # the name of the game being played for log files
CONFIG = 'nothreshold'
ACTIONS = 3 # number of valid actions
GAMMA = 0.9 # decay rate of past observations
OBSERVATION = 1000. # timesteps to observe before training
EXPLORE = 12000. # frames over which to anneal epsilon
FINAL_EPSILON = 0.1 # final value of epsilon
INITIAL_EPSILON = 1 # starting value of epsilon
REPLAY_MEMORY = 10000 # number of previous transitions to remember
BATCH = 16 #32 # size of minibatch
FRAME_PER_ACTION = 1

NEG_REGRET_FRAMES = 10
#OpenHexagonEmulator.configure()

img_rows , img_cols = G.x_size_final, G.y_size_final

print('Resolution: ', img_rows, img_cols)
#Convert image into Black and white
img_channels = 4 #We stack 4 frames




#==============================================================================
# CNN model structure (Unmodified)
#==============================================================================
def buildmodel():
    print("Now we build the model")
    
    model = Sequential()
    
    model.add(Convolution2D(16, 8, 8, subsample=(4,4),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same',input_shape=(img_channels,img_rows,img_cols)))
    model.add(Activation('relu'))
    
    #model.add(Convolution2D(64, 5, 5, subsample=(1,1),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same'))
    #model.add(Activation('relu'))
    
    #model.add(Convolution2D(64, 3, 3, subsample=(1,1),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same'))
    #model.add(Activation('relu'))
    
    #model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Convolution2D(32, 4, 4, subsample=(2,2),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same'))
    model.add(Activation('relu'))
    
    #model.add(Convolution2D(64, 3, 3, subsample=(1,1),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same'))
    #model.add(Activation('relu'))
    
    #model.add(Convolution2D(64, 4, 4, subsample=(2,2),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same'))
    #model.add(Activation('relu'))
    
    #model.add(MaxPooling2D(pool_size=(2, 2)))
    #model.add(Convolution2D(16, 3, 3, subsample=(1,1),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same'))
    #model.add(Activation('relu'))
    #model.add(MaxPooling2D(pool_size=(2, 2)))
    #model.add(Convolution2D(16, 3, 3, subsample=(1,1),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same'))
    #model.add(Activation('relu'))
    #model.add(MaxPooling2D(pool_size=(2, 2)))
    #model.add(Activation('relu'))
    #model.add(Convolution2D(64, 16, 16, subsample=(4,4),init=lambda shape, name: normal(shape, scale=0.01, name=name), border_mode='same'))
    #model.add(Activation('relu'))
    model.add(Flatten())
    model.add(Dense(256, init=lambda shape, name: normal(shape, scale=0.01, name=name)))
    model.add(Activation('relu'))
    #model.add(Dropout(0.1))
    model.add(Dense(ACTIONS,init=lambda shape, name: normal(shape, scale=0.01, name=name)))
    
    adam = Adam(lr=1e-6)
    model.compile(loss='mse',optimizer=adam)
    print("We finish building the model")
    print(model.summary())
    G.model = model
    #print(model.layers)
    return model
#==============================================================================

def prepareImage(image):
    tmpImage = skimage.color.rgb2gray(image)
    #thresh = skimage.filters.threshold_otsu(tmpImage)
    #tmpImage = tmpImage > thresh
    tmpImage = skimage.transform.resize(tmpImage,(img_rows , img_cols))
            
    
    tmpImage = skimage.exposure.rescale_intensity(tmpImage, out_range=(0, 255))
    
    #print(tmpImage)
    #if t % 100 == 0:
    #    img = smp.toimage(tmpImage)
    #    #img.show()
    #    smp.imsave('outfile' + str(t) + '.png', img)
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

    # get the first state by doing nothing and preprocess the image to 80x80x4
    do_nothing = np.zeros(ACTIONS)
    do_nothing[0] = 1
    x_t, r_0, terminal = gameState('enter')#game_state.frame_step(do_nothing)
    #print(x_t.shape)
    x_t = prepareImage(x_t)
    #print(x_t.shape)
    
    #s_t = np.reshape(x_t, (1, 1, 1, img_rows, img_cols))
    stacking = [x_t for i in range(img_channels)]
    s_t = np.stack(stacking, axis=0)
    #print(s_t.shape)
    #s_t = np.stack((x_t), axis=0)
    
    #s_t = np.reshape(x_t, (1, 1, 1, img_rows, img_cols))
    #print(s_t.shape)
    
    #print(s_t.shape)
    #In Keras, need to reshape
    #print(s_t.shape)
    s_t = s_t.reshape(1, s_t.shape[0], s_t.shape[3], s_t.shape[4])
    #print(s_t.shape)
    #print(s_t.shape)
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
    global t
    t = 0
    t_saved = 0
    run_count = -1
    saveIterator = 0
    saveThreshold = 10000
    framerate = 60 # Temp
    survival_times = []
    survival_times_last_10 = []
    survival_times_full_mean = []
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
        prev_time = 0
        while alive == True:
            step_time = time.time()
            if step_time - prev_time < 1/60: # Cap to 30 FPS
                time.sleep(1/60 - (step_time - prev_time))
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
            #s_t1 = x_t1
            
            # store the transition in D
            if current_run_frames > framerate*4: # Don't store early useless frames
                t_saved += 1
                D.append([s_t, action_index, r_t, s_t1, terminal])
                if terminal == 1:
                    for i in range(NEG_REGRET_FRAMES):
                        D[-2-i][2] = G.REWARD_TERMINAL/(i+2)
                    #D[-(NEG_REGRET_FRAMES+1):-1][3] += G.REWARD_TERMINAL
                if len(D) > REPLAY_MEMORY:
                    D.popleft()
            else:
                useRate = useRate + a_t
            #elif current_run_frames > framerate*4 - 1:
                #print('hi')
    
            
    
            s_t = s_t1
            t = t + 1
            current_run_frames += 1
            saveIterator += 1
    
            
    
            # print info
            state = ""
            if t_saved <= OBSERVE:
                state = "observe"
            elif t_saved > OBSERVE and t_saved <= OBSERVE + EXPLORE:
                state = "explore"
            else:
                state = "train"
            """
            if t % 1000 == 0:
                print("TS", t, "/ S", state, \
                    "/ E %.2f" % epsilon + " / A", action_index, "/ R", r_t)
            """
            if terminal == 1:
                # Lost!
                alive = 0
                
            if current_run_frames > 50000:
                # Likely stuck, just go to new level
                print('Stuck! Moving on...')
                alive = 0
                
            prev_time = step_time
            
        
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
        survival_times_last_10.append(np.mean(survival_times[-10:]))
        survival_times_full_mean.append(np.mean(survival_times))
        print('Run ' + str(run_count) + ' survived ' + "%.2f" % survival_time + 's' + ', %.2f fps' % framerate + ', key: ', ['%.2f' % k for k in useRate])
        print('\tMean: %.2f' % np.mean(survival_times), 'Last 10: %.2f' % survival_times_last_10[-1], 'Max: %.2f' % np.max(survival_times), "TS", t, "E %.2f" % epsilon)
        # Now Train!
        #only train if done observing
        if t_saved > OBSERVE:
            loss = 0
            Q_sa = 0
            #sample a minibatch to train on
            minibatch = random.sample(D, BATCH)
            for frame in range(NEG_REGRET_FRAMES):
                minibatch.append(D[-frame-1])

            inputs = np.zeros([len(minibatch), s_t.shape[1], s_t.shape[2], s_t.shape[3]])   #32, 80, 80, 4
            targets = np.zeros([inputs.shape[0], ACTIONS])                        #32, 2
            
            
            
            #Now we do the experience replay
            for i in range(0, len(minibatch)):
                state_t = minibatch[i][0]
                action_t = minibatch[i][1]   #This is action index
                reward_t = minibatch[i][2]
                state_t1 = minibatch[i][3]
                terminal = minibatch[i][4]
                # if terminated, only equals reward
                
                inputs[i:i + 1] = state_t    #I saved down s_t

                targets[i] = model.predict(state_t)  # Hitting each buttom probability
                Q_sa = model.predict(state_t1)

                if terminal:
                    targets[i, action_t] = reward_t
                else:
                    targets[i, action_t] = reward_t + GAMMA * np.max(Q_sa)

            print("\tQ_MAX " , np.max(Q_sa), "/ L ", loss)
            #print(targets)
                    
            # targets2 = normalize(targets)
            loss += model.train_on_batch(inputs, targets)        
    
            if saveIterator >= saveThreshold:
                saveIterator = 0
                # save progress every 10000 iterations
                print("Saving Model...")
                model.save_weights("model.h5", overwrite=True)
                with open("model.json", "w") as outfile:
                    json.dump(model.to_json(), outfile)
    
            with open("log.txt", "a+") as outf:
                outf.write('%d,%.10f,%.10f,%.10f\n' % (run_count, np.max(Q_sa), loss, survival_time))
                
            graphHelper.graphSimple([np.arange(run_count+1),np.arange(run_count+1),np.arange(run_count+1)], [survival_times, survival_times_last_10, survival_times_full_mean], ['DQN', 'DQN_Last_10_Mean', 'DQN_Full_Mean'], 'DQN on Open Hexagon', 'Time(s)', 'Run', savefigName="DQN_graph")
        
        with open("DQN.txt", "a+") as outf:
            outf.write('%d,%.10f,%.10f,%.10f\n' % (run_count, survival_times[-1], survival_times_last_10[-1], survival_times_full_mean[-1]))    
            
        #print(np.arange(run_count))
        #print(survival_times)
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
