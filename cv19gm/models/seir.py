#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEIR Model
"""

import numpy as np
from scipy.integrate import solve_ivp
import pandas as pd
#from datetime import datetime
from datetime import timedelta

# cv19gm libraries 
#import os
#import sys
#path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
#sys.path.insert(1, path)

#import cv19gm.data.cv19data as cv19data
#import cv19gm.utils.cv19timeutils as cv19timeutils
#import cv19gm.utils.cv19functions as cv19functions
import cv19gm.utils.cv19files as cv19files


class SEIR:
    """
        SEIR model object:
        Construction:
            SEIR(self, config = None, inputdata=None)

    """
    def __init__(self, config = None, inputdata=None,verbose = False, **kwargs):
        self.model = "SEIR"
        
        if not config:
            print('Missing configuration file, using default')
            #raise('Missing configuration file')
            #return None
                
        # ------------------------------- #
        #         Parameters Load         #
        # ------------------------------- #        
        if verbose:
            print('Loading configuration file')          
        cv19files.loadconfig(self,config,inputdata,**kwargs)
        if verbose:
            print('Initializing parameters and variables')
        self.set_relational_values()
        if verbose:
            print('Building equations')          
        self.set_equations()

        self.solved = False
        if verbose:
            print('SEIR object created')

    # ------------------- #
    #  Valores Iniciales  #
    # ------------------- #
   
    def set_relational_values(self):
        # Active infected
        if hasattr(self,'I_det'):
            self.I = self.I_det/self.pI_det
        else:
            self.I_det = self.I*self.pI_det


        # New daily Infected
        if hasattr(self,'I_d_det'):
            self.I_d = self.I_d_det/self.pI_det
        else:
            self.I_d_det = self.I_d*self.pI_det


        # Accumulated Infected
        if hasattr(self,'I_ac_det'):
            self.I_ac = self.I_ac_det/self.pI_det
        else:
            self.I_ac_det = self.I_ac*self.pI_det

        
        # Exposed
        #if not self.Einit:
        if not hasattr(self,'E'):
            self.E = self.mu*self.I
        elif not self.E:
            self.E = self.mu*self.I

        if not hasattr(self,'E_d'):
            self.E_d=self.mu*self.I_d
        elif not self.E_d:
            self.E_d=self.mu*self.I_d

        if not hasattr(self,'E_ac'):    
            self.E_ac=self.mu*self.I_ac
        elif not self.E_ac:
            self.E_ac=self.mu*self.I_ac
       
        # Valores globales
        if not hasattr(self,'popfraction'):
            self.popfraction = 1
        
        self.N = self.popfraction*self.population
        self.S = self.N-self.E-self.I-self.R

        # External flux functions: 
        if not hasattr(self,'S_f'):
            self.S_f = lambda t:0
        
        if not hasattr(self,'E_f'):
            self.E_f = lambda t:0

        if not hasattr(self,'I_f'):
            self.I_f = lambda t:0
        
        if not hasattr(self,'R_f'):
            self.R_f = lambda t:0

        # Saturation kinetics
        if not hasattr(self,'k_I'):
            self.k_I=0

        if not hasattr(self,'k_R'):
            self.k_R=0            

    def set_equations(self):
        """        
        Sets Diferential Equations
        """
        # --------------------------- #
        #        Susceptibles         #
        # --------------------------- #
       
        # 0) dS/dt:
        self.dS = lambda t,S,E,I,R: self.S_f(t) - self.alpha(t)*self.beta(t)*S*I/(self.N+self.k_I*I + self.k_R*R) + self.rR_S(t)*R
        
        # --------------------------- #
        #           Exposed           #
        # --------------------------- #     
        
        # 1) dE/dt
        self.dE = lambda t,S,E,I,R: self.E_f(t) + self.alpha(t)*self.beta(t)*S*I/(self.N+self.k_I*I + self.k_R*R) - E/self.tE_I(t)
 
        # 2) Daily dE/dt
        self.dE_d = lambda t,S,E,E_d,I,R: self.E_f(t) + self.alpha(t)*self.beta(t)*S*I/(self.N+self.k_I*I + self.k_R*R) - E_d

        # --------------------------- #
        #           Infected          #
        # --------------------------- #                
        
        
        # 3) Active
        self.dI=lambda t,E,I: self.I_f(t) + E/self.tE_I(t) - I/self.tI_R(t)
        
        # 4) New Daily
        self.dI_d = lambda t,E,I_d: self.I_f(t) + E/self.tE_I(t) - I_d 

        # --------------------------- #
        #         Recovered           #
        # --------------------------- #  
        
        # 5) Total recovered
        self.dR=lambda t,I,R: self.R_f(t) + I/self.tI_R(t) - self.rR_S(t)*R

        # 6) Recovered per day
        self.dR_d=lambda t,I,R_d: self.R_f(t) + I/self.tI_R(t) - R_d

        # 7) External Flux:
        self.dFlux = lambda t: self.S_f(t) + self.E_f(t) + self.I_f(t) + self.R_f(t) 

    def integrate(self,t0=0,T=None,h=0.01,method='LSODA'):
        print('The use of integrate() is now deprecated. Use solve() instead.')
        self.solve(t0=t0,T=T,h=h,method=method)

    def run(self,t0=0,T=None,h=0.01,method='LSODA'):
        #print('The use of integrate() is now deprecated. Use solve() instead.')
        self.solve(t0=t0,T=T,h=h,method=method)

    # Scipy
    def solve(self,t0=0,T=None,h=0.01,method='LSODA'):
        """
        Solves ODEs using scipy.integrate
        Args:
            t0 (int, optional): Initial time. Defaults to 0.
            T ([type], optional): Endtime. Defaults to time given when building the object
            h (float, optional): Time step. Defaults to 0.01.            
        """

        if T is None:
            T = self.tsim

        # Check if we already simulated the array
        if self.solved:
            #print('Already solved')
            return()
        
        self.t=np.arange(t0,T+h,h)
        initcond = np.array([self.S,self.E,self.E_d,self.I,self.I_d,self.R,0,0]) # [S0,E0,E_d0,I0,I_d0,R0,R_d0,Flux0]
        
        sol = solve_ivp(self.model_SEIR_graph,(t0,T), initcond,method=method,t_eval=list(range(t0,T)))
        
        self.sol = sol
        self.t=sol.t 
        
        self.S=sol.y[0,:]
        self.E=sol.y[1,:]
        self.E_d=sol.y[2,:]
        self.I=sol.y[3,:]
        self.I_d=sol.y[4,:]
        self.R=sol.y[5,:]
        self.R_d=sol.y[6,:]
        self.Flux=sol.y[7,:]

        self.E_ac = np.cumsum(np.concatenate([np.array([self.E_ac]),self.E_d[:-1]]))
        self.I_ac = np.cumsum(np.concatenate([np.array([self.I_ac]),self.I_d[:-1]]))  
        self.R_ac = np.cumsum(np.concatenate([np.array([self.R[0]]),self.R_d[:-1]]))

        self.I_det = self.I*self.pI_det
        self.I_d_det = self.I_d*self.pI_det
        self.I_ac_det = self.I_ac*self.pI_det

        self.analytics()
        self.df_build()
        self.solved = True

        return 

    def model_SEIR_graph(self,t,y):
        ydot=np.zeros(len(y))
        ydot[0]=self.dS(t,y[0],y[1],y[3],y[5])

        ydot[1]=self.dE(t,y[0],y[1],y[3],y[5])
        ydot[2]=self.dE_d(t,y[0],y[1],y[2],y[3],y[5])

        ydot[3]=self.dI(t,y[1],y[3])
        ydot[4]=self.dI_d(t,y[1],y[4])

        ydot[5]=self.dR(t,y[3],y[5])
        ydot[6]=self.dR_d(t,y[3],y[6])

        ydot[7]=self.dFlux(t)      
                                        
        return(ydot)

    def analytics(self):
        """
        Perform simulation analytics after running it.
        It calculates peaks, prevalence, and will include R(t). 
        """
        #Cálculo de la fecha del Peak  
        self.peakindex = np.where(self.I==max(self.I))[0][0]
        self.peak = max(self.I)
        self.peak_t = self.t[self.peakindex]
        if self.initdate:
            self.dates = [self.initdate+timedelta(int(self.t[i])) for i in range(len(self.t))]
            self.peak_date = self.initdate+timedelta(days=int(round(self.peak_t)))
        else:
            self.dates = [None for i in range(len(self.t))]
            self.peak_date = None            

        # Prevalence: 
        self.prevalence_total = self.I_ac/self.population
        self.prevalence_susc = [self.I_ac[i]/(self.S[i]+self.E[i]+self.I[i]+self.R[i]) for i in range(len(self.I_ac))]
        self.prevalence_det = [self.pI_det*self.I_ac[i]/(self.S[i]+self.E[i]+self.I[i]+self.R[i]) for i in range(len(self.I_ac))]                         
        return
       
    def df_build(self):
        """
        Builds a dataframe with the simulation results
        """
        self.results = pd.DataFrame({'t':self.t,'dates':self.dates})
        names = ['S','E','E_d','I','I_d','R','R_d','Flux']
        aux = pd.DataFrame(np.transpose(self.sol.y),columns=names).astype(int)
        names2 = ['E_ac','I_ac','R_ac','I_det','I_d_det','I_ac_det']#,'prevalence_total','prevalence_susc','prevalence_det']
        vars2 = [self.E_ac,self.I_ac,self.R_ac,self.I_det,self.I_d_det,self.I_ac_det]#,self.prevalence_total,self.prevalence_susc,self.prevalence_det]
        aux2 = pd.DataFrame(np.transpose(vars2),columns=names2).astype(int)
        
        # Prevalence
        self.prevalence = pd.DataFrame(np.transpose([self.prevalence_total,self.prevalence_susc,self.prevalence_det]),columns = ['prevalence_total','prevalence_susc','prevalence_det'])
        
        # Parameters
        nameparams = ['beta','alpha','tE_I','tI_R','rR_S']
        beta_val = [self.beta(t) for t in self.t]
        alpha_val = [self.alpha(t) for t in self.t]
        tE_I_val = [self.tE_I(t) for t in self.t]
        tI_R_val = [self.tI_R(t) for t in self.t]
        rR_S_val = [self.rR_S(t) for t in self.t]
        self.params = pd.DataFrame(np.transpose([beta_val,alpha_val,tE_I_val,tI_R_val,rR_S_val]),columns = nameparams)
        
        # Build final Dataframe
        self.compartments = pd.concat([self.results,aux,aux2],axis=1)
        self.results = pd.concat([self.results,aux,aux2,self.params,self.prevalence],axis=1)
        #self.results = self.results.astype({'S': int,'E': int,'E_d': int,'I': int,'I_d': int,'R': int,'R_d': int,'E_ac': int,'I_ac': int,'R_ac': int,'I_det': int,'I_d_det': int,'I_ac_det': int})

        self.resume = pd.DataFrame({'peak':int(self.peak),'peak_t':self.peak_t,'peak_date':self.peak_date},index=[0])
        return    


    """
 
    def calculateindicators(self):
        self.R_ef
        self.SHFR

        # SeroPrevalence Calculation

        # Errors (if real data)

        # Active infected
        print('wip')

    def resume(self):        
        print("Resumen de resultados:")
        qtype = ""
        for i in range(self.numescenarios):
            if self.inputarray[i][-1]==0:
                qtype = "Cuarentena total"
            if self.inputarray[i][-1]>0:
                qtype ="Cuarentena Dinámica"            

            print("Escenario "+str(i))
            print("Tipo de Cuarentena: "+qtype+'\nmov_rem: '+str(self.inputarray[i][2])+'\nmov_max: '+str(self.inputarray[i][2])+
            "\nInicio cuarentena: "+(self.initdate+timedelta(days=self.inputarray[i][4])).strftime('%Y/%m/%d')+"\nFin cuarentena: "+(self.initdate+timedelta(days=self.inputarray[i][5])).strftime('%Y/%m/%d'))
            print("Peak infetados \n"+"Peak value: "+str(self.peak[i])+"\nPeak date: "+str(self.peak_date[i]))
            print("Fallecidos totales:"+str(max(self.B[i])))
            print("Fecha de colapso hospitalario \n"+"Camas: "+self.H_colapsedate[i]+"\nVentiladores: "+self.V_colapsedate[i])
            print("\n")
    """

        
