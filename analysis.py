#! /usr/bin/env python

"""sklearn analysis"""

import datetime

import numpy as np
import cPickle as pickle
from sklearn import cross_validation
from optparse import OptionParser

from data_handle import Data_Handle
from classifier import *
from trader import *

from IPython import embed
#embed() # this call anywhere in your program will start IPython

np.set_printoptions(precision=3, threshold=50, linewidth=100)		

def create_dummy_files(fnames):
	"""generate dummy analysis events from complete events"""
	
	for fname in fnames:
		
		with open(fname,'rb')as inputfile: 
			
			event = pickle.load(inputfile)
			
			for k in event['data'].keys():
				
				new_data = []
				for item in event['data'][k]:
					
					if ( event['time_e'] - item[0] ) > datetime.timedelta(minutes=35):
						new_data.append(item)
				event['data'][k] = new_data
				
		with open(fname,'wb') as outputfile: 
			pickle.dump(event,outputfile,pickle.HIGHEST_PROTOCOL)		
			

class Analysis():
	
	def __init__(self,limits,max_price,cut_pars,verbose=True):
		
		if verbose: 
			print 'fitting methods to dataset:\nlimits=[%.2f,%.2f]\n' % (limits[0],limits[1])
			
		#~ self.limit=float(limit)
		self.limits=limits
		self.max_price=float(max_price)
		self.cut_pars=cut_pars
		
		#load datalist from file
		datalist = Data_Handle().load_data(verbose=verbose).get_datalist()
		
		#~ #randomize sample
		#~ np.random.shuffle(datalist)
		
		#get lists (names,features,etc...)
		runner_names,feature_names,features,result = DataML().get_lists(datalist,max_price=self.max_price,cut_pars=self.cut_pars,verbose=verbose)
		
		#prepare data for classifiers
		self.x,self.y = prepareData(features,result,limits=self.limits)
		
		#split in train and test samples (not random!!!)
		self.xtrain,self.xcontrol,self.ytrain,self.ycontrol = cross_validation.train_test_split(self.x,self.y,test_size=0.2,random_state=42)
		if verbose:
			print '  Samples (limits=[%.2f,%.2f], max_price=%.1f):\n  train: %d\n  control: %d\n' % (self.limits[0],self.limits[1],self.max_price,len(self.x),len(self.xcontrol))	
		
		self.clf = Classifier()

	def fit(self):
	
		self.clf.fit(self.xtrain,self.ytrain)
		
	def performance(self):
		
		out = self.clf.performance_values(self.xcontrol,self.ycontrol)
		return out

	def test(self,datalist,num=3):
		
		print 'testing algorithms on selected events %d times' % num
		
		#get lists (names,features,etc...)
		runner_names,feature_names,features,result = DataML().get_lists(datalist,max_price=self.max_price,cut_pars=self.cut_pars)	

		#prepare data for classifiers
		x,y = prepareData(features,result,limits=self.limits)
		
		#test num times
		scores,subsets = {},{}
		for i in xrange(num):
			
			#train clfs
			self.fit()
			
			#test clfs
			for k in sorted(self.clf.clfs.keys()):
				if not getattr(self.clf.clfs[k],"score_values",None)==None:
					if not scores.has_key(k):
						scores[k] = np.array([])
						subsets[k] = np.array([])
					
					scores[k] = np.append( scores[k], self.clf.clfs[k].score_values(x,y) )
					subsets[k] = np.append( subsets[k], self.clf.clfs[k].get_size_subset_values(x) )
	
		out = '  test algorithms (ignoring result==0):\n'
		for k in sorted(scores.keys()):
			scores[k][np.isnan(scores[k])==True] = 0
			out += "  %s:	%0.2f -> subset=%0.2f\n" % (k.ljust(5,' '),scores[k].mean(),subsets[k].mean())
		out+='\n'
		print out		
		
	def predict(self,link,datalist,verbose=True):			
		
		out = ''
		
		#get lists (names,features,etc...)
		runner_names,feature_names,features,result = DataML().get_lists(datalist,max_price=self.max_price,cut_pars=self.cut_pars)	
		
		#skip event if not enough data
		if len(features)==0:
			print '  WARNING: not enough usable data to predict event\n'
					
		#classification
		else:
		
			#prepare data for classifiers
			x = np.array(features)
			
			c_ym  = self.clf.clfs['combi'].predict(x) 
			t_ym,t_pm = self.clf.clfs['ptree'].predict_proba(x)
			k_ym,k_pm = self.clf.clfs['pknn'].predict_proba(x)
			
			c_ym[np.isnan(c_ym)] = 0
			t_ym[np.isnan(t_ym)] = 0
			t_pm[np.isnan(t_pm)] = 0
			k_ym[np.isnan(k_ym)] = 0
			k_pm[np.isnan(k_pm)] = 0
			
			#prediction possible
			if np.any(c_ym)!=0 or np.any(t_ym)!=0 or np.any(k_ym)!=0:
				
				price = x[:,feature_names.index("last")]
				
				array = np.array(zip(runner_names,c_ym,t_ym,t_pm,k_ym,k_pm,price),
				dtype=[('name','S30'),('c_ym',int),('t_ym',int),('t_pm',float),('k_ym',int),('k_pm',float),('price',float)])		
						
				#~ array[::-1].sort(order=['t_ym','t_pm'])	#reverse sort
				array.sort(order=['price'])
				
				#output succesful prediction
				out += '  url:  %s\n' % link
				out += '  %s    %s   %s          %s          %s\n' %(' '.ljust(20,' '), 'c','t','k','price')
				for i,item in enumerate(array):
					out += '  %s:  %2d  %2d (%.2f)  %2d (%.2f)   %5.2f\n' % (item['name'][:20].ljust(20,' '),item['c_ym'],item['t_ym'],item['t_pm'],item['k_ym'],item['k_pm'],item['price'])
				
			else:
				print '  WARNING: no prediction possible (%s)\n' % link
				
		return out  
			
	def cross_validation(self):
		
		self.clf.cross_validation_clfs_values(self.xtrain,self.ytrain,num_cv=5)

def load_pars(fname = 'parameters_analysis.pkl'):	
	with open(fname,'rb')as inputfile: 
		pars = pickle.load(inputfile)
	return pars
			
def main():
	print 'here starts main program'

	#parse options
	parser = OptionParser()
	parser.add_option("--cv", dest="cv", action="store_true", default=False,
	                  help="cross validate methods with dataset")
	parser.add_option("--test", dest="test", action="store_true", default=False,
	                  help="test methods with specific events")
	(options, args) = parser.parse_args()

	#load parameters
	pars = load_pars()
	cut_pars = [ 60,4,24 ]
	
	pars = pars[:1]
	
	output='\n\nResult:\n\n'	
	for par in pars:	
	
		#init analysis object
		analysis = Analysis(limits=par,max_price=5,cut_pars=cut_pars)
		
		if options.cv:
			
			#perform cross validation
			analysis.cross_validation()
		
		else:
			#get filenames
			if len(args)<1:
				raise NameError("Usage: %s /path_some_file")
			else: fnames=args

			#load event data from fnames
			dh = Data_Handle().cut_raw_data(fnames=fnames,analysis=True)
			linklist = dh.get_linklist()
			datalist = dh.get_datalist()
			
			if options.test:
				analysis.test(datalist,num=50)
				
			else:	
				#predict outcome events
				print 'Predicting outcome events:\n'
				
				#train clf with existing data
				analysis.fit()
				
				outputs = []
				for i in xrange(len(datalist)):
					
					data = datalist[i]
					link = linklist[i]
					
					out = analysis.predict(link,[data])
					
					if out!='': outputs.append(out)
	
				output += 'limits=[%.2f,%.2f]\n%d of %d events with prediction:\n\n' % (par[0],par[1],len(outputs),len(datalist))
				if len(outputs)>0:
					output += analysis.performance()
					for i,item in enumerate(outputs):
						output += '  event #%d:\n%s\n' % (i+1,item)
					output += '\n'

	if options.cv==False and options.test==False:
		print output	
		#~ embed()
		
if __name__ == "__main__":
    main()		

