#include "Cross.h"
#include "GridVel.h"
#include "OUtils.h"
#include "Uncertainty.h"

#ifdef MAC
#ifdef MPW
#pragma SEGMENT TCURRENTMOVER
#endif
#endif



static PopInfoRec csPopTable[] = {
		{ M16, nil, M16LATDIR, 0, pNORTHSOUTH1, 0, 1, FALSE, nil },
		{ M16, nil, M16LONGDIR, 0, pEASTWEST1, 0, 1, FALSE, nil }
	};

///////////////////////////////////////////////////////////////////////////

TCurrentMover::TCurrentMover (TMap *owner, char *name) : TMover(owner, name)
{
	// set fields of our base class
	fDuration=48*3600; //48 hrs as seconds 
	fUncertainStartTime = 0;
	fTimeUncertaintyWasSet = 0;
	
	fDownCurUncertainty = -.3;  // 30%
	fUpCurUncertainty = .3; 	
	fRightCurUncertainty = .1;  // 10%
	fLeftCurUncertainty= -.1; 

	fLESetSizesH = 0;
	fUncertaintyListH = 0;

	bIAmPartOfACompoundMover = false;
	bIAmA3DMover = false;
}


///////////////////////////////////////////////////////////////////////////

OSErr TCurrentMover::UpItem(ListItem item)
{
	long i, n;
	TMover* mover;
	TMap* map;
	OSErr err = 0;
	
	if (item.index == I_CATSNAME)	// check others too
	{

		if (bIAmPartOfACompoundMover)
		{
			if (moverMap->bIAmPartOfACompoundMap)	// do the map swap here too?
				map = (TMap*)GetPtCurMap();
			else map = moverMap;
			//for (i = 0, n = moverMap->moverList->GetItemCount() ; i < n ; i++) {
				//moverMap->moverList->GetListItem((Ptr)&mover, i);
			for (i = 0, n = map->moverList->GetItemCount() ; i < n ; i++) {
				map->moverList->GetListItem((Ptr)&mover, i);
				if (mover->IAm(TYPE_COMPOUNDMOVER))
				{
					if (!(((TCompoundMover*)mover)->moverList->IsItemInList((Ptr)&item.owner, &i))) 
						continue;
					else
					{
						if (i>0) {
							if (err = ((TCompoundMover*)mover) -> moverList -> SwapItems(i, i - 1))
								{ TechError("TCurrentMover::UpItem()", "mover -> moverList -> SwapItems()", err); return err; }
							SelectListItem(item);
							InvalListLength();// why ? JLM
							if (moverMap->bIAmPartOfACompoundMap)
							{
								if (err = (dynamic_cast<TCompoundMap *>(map)) -> mapList -> SwapItems(i, i - 1))
									{ TechError("TCurrentMover::UpItem()", "map -> mapList -> SwapItems()", err); return err; }
								model->NewDirtNotification();
							}

							return 0;
						}
					}
				}
			}
			return false;
		}

/*for (i = 0, n = moverMap->moverList->GetItemCount() ; i < n ; i++) {
			moverMap->moverList->GetListItem((Ptr)&mover, i);
			if (mover->IAm(TYPE_COMPOUNDMOVER))
			{
				if (!(((TCompoundMover*)mover)->moverList->IsItemInList((Ptr)&item.owner, &i))) 
					return FALSE;
				else
				{
					if (i>0) {
						if (err = ((TCompoundMover*)mover) -> moverList -> SwapItems(i, i - 1))
							{ TechError("TCurrentMover::UpItem()", "mover -> moverList -> SwapItems()", err); return err; }
						SelectListItem(item);
						InvalListLength();// why ? JLM
						return 0;
					}
				}
			}
			else continue;
		}*/
	}

	return TMover::UpItem(item);
}

OSErr TCurrentMover::DownItem(ListItem item)
{
	long i, n;
	TMover* mover;
	TMap* map;
	OSErr err = 0;

	if (item.index == I_CATSNAME)	// check others too
	{
	
		if (bIAmPartOfACompoundMover)
		{
			if (moverMap->bIAmPartOfACompoundMap)	// do the map swap here too?
				map = (TMap*)GetPtCurMap();
			else map = moverMap;
			//for (i = 0, n = moverMap->moverList->GetItemCount() ; i < n ; i++) {
				//moverMap->moverList->GetListItem((Ptr)&mover, i);
			for (i = 0, n = map->moverList->GetItemCount() ; i < n ; i++) {
				map->moverList->GetListItem((Ptr)&mover, i);
				if (mover->IAm(TYPE_COMPOUNDMOVER))
				{
					if (!(((TCompoundMover*)mover)->moverList->IsItemInList((Ptr)&item.owner, &i))) 
						continue;
					else
					{
						if (i<(((TCompoundMover*)mover)->moverList->GetItemCount() - 1)) {
							if (err = ((TCompoundMover*)mover) -> moverList -> SwapItems(i, i + 1))
								{ TechError("TCurrentMover::DownItem()", "mover -> moverList -> SwapItems()", err); return err; }
							SelectListItem(item);
							InvalListLength();// why ? JLM
							if (moverMap->bIAmPartOfACompoundMap)
							{
								if (err = (dynamic_cast<TCompoundMap *>(map)) -> mapList -> SwapItems(i, i + 1))
									{ TechError("TCurrentMover::DownItem()", "map -> mapList -> SwapItems()", err); return err; }
								model->NewDirtNotification();
							}
							return 0;
						}
					}
				}
				
			}
			return false;
		}
		/*for (i = 0, n = moverMap->moverList->GetItemCount() ; i < n ; i++) {
			moverMap->moverList->GetListItem((Ptr)&mover, i);
			if (mover->IAm(TYPE_COMPOUNDMOVER))
			{
				if (!(((TCompoundMover*)mover)->moverList->IsItemInList((Ptr)&item.owner, &i))) 
					return FALSE;
				else
				{
					if (i<(((TCompoundMover*)mover)->moverList->GetItemCount() - 1)) {
						if (err = ((TCompoundMover*)mover) -> moverList -> SwapItems(i, i + 1))
							{ TechError("TCurrentMover::UpItem()", "mover -> moverList -> SwapItems()", err); return err; }
						SelectListItem(item);
						InvalListLength();// why ? JLM
						return 0;
					}
				}
			}
			else continue;
		}*/
	}

	return TMover::DownItem(item);
}

Boolean TCurrentMover::FunctionEnabled(ListItem item, short buttonID)
{
	long i,n,j,num;
	TMover* mover;
	TMover* mover2;
	TMap* map;
	switch (item.index) {
		case I_CATSNAME:
			switch (buttonID) {
				case ADDBUTTON: return FALSE;
				case DELETEBUTTON: return TRUE;
				case UPBUTTON:
				case DOWNBUTTON:
				// need a way to check if mover is part of a Compound Mover - thinks it's just a currentmover

				if (!bIAmPartOfACompoundMover)
					return TMover::FunctionEnabled(item, buttonID);
					
				if (moverMap->bIAmPartOfACompoundMap)
					map = (TMap*)GetPtCurMap();
				else map = moverMap;
				//for (i = 0, n = moverMap->moverList->GetItemCount() ; i < n ; i++) {
					//moverMap->moverList->GetListItem((Ptr)&mover, i);
				for (i = 0, n = map->moverList->GetItemCount() ; i < n ; i++) {
					map->moverList->GetListItem((Ptr)&mover, i);
					if (mover->IAm(TYPE_COMPOUNDMOVER))
					{
						for (j = 0, num = ((TCompoundMover*)mover)->moverList->GetItemCount() ;  j < num; j++)
						{
							((TCompoundMover*)mover)->moverList->GetListItem((Ptr)&mover2, j);
							if (mover2==this)
							if (!(((TCompoundMover*)mover)->moverList->IsItemInList((Ptr)&item.owner, &j))) 
								//return FALSE;
								continue;
							else
							{
								switch (buttonID) {
									case UPBUTTON: return j > 0;
									case DOWNBUTTON: return j < (((TCompoundMover*)mover)->moverList->GetItemCount()-1);
								}
							}
						}
					}
				}
					
			/*if (!moverMap->moverList->IsItemInList((Ptr)&item.owner, &i)) return FALSE;
			switch (buttonID) {
				case UPBUTTON: return i > 0;
				case DOWNBUTTON: return i < (moverMap->moverList->GetItemCount() - 1);
			}
			break;*/
		}
	}
	
	if (buttonID == SETTINGSBUTTON) return TRUE;
	
	return TMover::FunctionEnabled(item, buttonID);
}
///////////////////////////////////////////////////////////////////////////

void TCurrentMover::UpdateUncertaintyValues(Seconds elapsedTime)
{
	long i,n;
	
	fTimeUncertaintyWasSet = elapsedTime;

	if(!fUncertaintyListH) return;
	
	n = _GetHandleSize((Handle)fUncertaintyListH)/sizeof(**fUncertaintyListH);

			
	for(i=0;i<n;i++)
	{
		LEUncertainRec localCopy;
		memset(&localCopy,0,sizeof(LEUncertainRec));
		
		if(fDownCurUncertainty<fUpCurUncertainty)
		{
			localCopy.downStream = 
				GetRandomFloat(fDownCurUncertainty,fUpCurUncertainty);
		}
		else
		{
			localCopy.downStream = 
				GetRandomFloat(fUpCurUncertainty,fDownCurUncertainty);
		}
		if(fLeftCurUncertainty<fRightCurUncertainty)
		{
			localCopy.crossStream = 
				GetRandomFloat(fLeftCurUncertainty,fRightCurUncertainty);
		}
		else
		{
			localCopy.crossStream = 
				GetRandomFloat(fRightCurUncertainty,fLeftCurUncertainty);
		}
		INDEXH(fUncertaintyListH,i) = localCopy;

	}	
}


OSErr TCurrentMover::AllocateUncertainty()
{
	long i,j,n,numrec;
	TOLEList *list;
	LEUncertainRecH h;
	OSErr err=0;
	CMyList	*LESetsList = model->LESetsList;
		
	this->DisposeUncertainty(); // get rid of any old values
	if(!LESetsList)return noErr;
	
	n = LESetsList->GetItemCount();
	if(!(fLESetSizesH = (LONGH)_NewHandle(sizeof(long)*n)))goto errHandler;
		
	for (i = 0,numrec=0; i < n ; i++) {
		(*fLESetSizesH)[i]=numrec;
		LESetsList->GetListItem((Ptr)&list, i);
		if(list->GetLEType()==UNCERTAINTY_LE) // JLM 9/10/98
			numrec += list->GetLECount();
	}
	if(!(fUncertaintyListH = 
			(LEUncertainRecH)_NewHandle(sizeof(LEUncertainRec)*numrec)))goto errHandler;
	
	return noErr;
errHandler:
	this->DisposeUncertainty(); // get rid of any values allocated
	TechError("TCurrentMover::AllocateUncertainty()", "_NewHandle()", 0);
	return memFullErr;
}

OSErr TCurrentMover::UpdateUncertainty(void)
{
	OSErr err = noErr;
	long i,n;
	Boolean needToReInit = false;
	Seconds elapsedTime =  model->GetModelTime() - model->GetStartTime();


	Boolean bAddUncertainty = (elapsedTime >= fUncertainStartTime) && model->IsUncertain();
	// JLM, this is elapsedTime >= fUncertainStartTime because elapsedTime is the value at the start of the step

	if(!bAddUncertainty)
	{	// we will not be adding uncertainty
		// make sure fWindUncertaintyList  && fLESetSizesH are unallocated
		if(fUncertaintyListH) this->DisposeUncertainty();
		return 0;
	}
	
	if(!fUncertaintyListH || !fLESetSizesH)
		needToReInit = true;
	
	if(elapsedTime < fTimeUncertaintyWasSet) 
	{	// the model reset the time without telling us
		needToReInit = true;
	}
	
	if(fLESetSizesH)
	{	// check the LE sets are still the same, JLM 9/18/98
		TLEList *list;
		long numrec;
		n = model->LESetsList->GetItemCount();
		i = _GetHandleSize((Handle)fLESetSizesH)/sizeof(long);
		if(n != i) needToReInit = true;
		else
		{
			for (i = 0,numrec=0; i < n ; i++) {
				if(numrec != (*fLESetSizesH)[i])
				{
					 needToReInit = true;
					 break;
				}
				model->LESetsList->GetListItem((Ptr)&list, i);
				if(list->GetLEType()==UNCERTAINTY_LE) // JLM 9/10/98
					numrec += list->GetLECount();
			}
		}
	
	}
	
	if(needToReInit)
	{
		err = this->AllocateUncertainty();
		if(!err) this->UpdateUncertaintyValues(elapsedTime);
		if(err) return err;
	}
	else if(elapsedTime >= fTimeUncertaintyWasSet + fDuration) // we exceeded the persistance, time to update
	{	
		this->UpdateUncertaintyValues(elapsedTime);
	}
	
	return err;
}


OSErr TCurrentMover::PrepareForModelStep()
{
	OSErr err = this->UpdateUncertainty();
	if (err) printError("An error occurred in TCurrentMover::PrepareForModelStep");
	return err;
}


void TCurrentMover::DisposeUncertainty()
{
	fTimeUncertaintyWasSet = 0;

	if (fUncertaintyListH)
	{
		DisposeHandle ((Handle) fUncertaintyListH);
		fUncertaintyListH = nil;
	}
	
	if (fLESetSizesH)
	{
		DisposeHandle ((Handle) fLESetSizesH);
		fLESetSizesH = 0;
	}
}

void TCurrentMover::Dispose ()
{
	
	this->DisposeUncertainty();
		
	TMover::Dispose ();
}


//#define TCurrentMoverREADWRITEVERSION 1 //JLM
#define TCurrentMoverREADWRITEVERSION 2 //JLM

OSErr TCurrentMover::Write (BFPB *bfpb)
{
	long i, version = TCurrentMoverREADWRITEVERSION; //JLM
	ClassID id = GetClassID ();
	OSErr err = 0;

	if (err = TMover::Write (bfpb)) return err;

	StartReadWriteSequence("TCurrentMover::Write()");
	if (err = WriteMacValue(bfpb, id)) return err;
	if (err = WriteMacValue(bfpb, version)) return err;

	if (err = WriteMacValue(bfpb,fDownCurUncertainty)) return err;
	if (err = WriteMacValue(bfpb,fUpCurUncertainty)) return err;
	if (err = WriteMacValue(bfpb,fRightCurUncertainty)) return err;
	if (err = WriteMacValue(bfpb,fLeftCurUncertainty)) return err;

	if (err = WriteMacValue(bfpb,bIAmPartOfACompoundMover)) return err;
	// code goes here, should we save the arrays of random numbers ?
	
	return err;
}

OSErr TCurrentMover::Read(BFPB *bfpb)
{
	long i, version;
	ClassID id;
	OSErr err = 0;
	
	if (err = TMover::Read(bfpb)) return err;
	
	StartReadWriteSequence("TCurrentMover::Read()");
	if (err = ReadMacValue(bfpb,&id)) return err;
	if (id != GetClassID ()) { TechError("TCurrentMover::Read()", "id != TYPE_CATSMOVER", 0); return -1; }
	if (err = ReadMacValue(bfpb,&version)) return err;
	if (version > TCurrentMoverREADWRITEVERSION) { printSaveFileVersionError(); return -1; }

	if (err = ReadMacValue(bfpb,&fDownCurUncertainty)) return err;
	if (err = ReadMacValue(bfpb,&fUpCurUncertainty)) return err;
	if (err = ReadMacValue(bfpb,&fRightCurUncertainty)) return err;
	if (err = ReadMacValue(bfpb,&fLeftCurUncertainty)) return err;
	
	if (version>1)
		if (err = ReadMacValue(bfpb,&bIAmPartOfACompoundMover)) return err;

	return err;
}

///////////////////////////////////////////////////////////////////////////
OSErr TCurrentMover::CheckAndPassOnMessage(TModelMessage *message)
{	// JLM
	char ourName[kMaxNameLen];
	
	// see if the message is of concern to us
	this->GetClassName(ourName);
	
	if(message->IsMessage(M_SETFIELD,ourName))
	{
		double val,val2;
		char str[256];
		OSErr err = 0;
		////////////////
		err = message->GetParameterAsDouble("DownCurUncertainty",&val);
		if(!err) { 
				this->fDownCurUncertainty = -val;
				err = message->GetParameterAsDouble("UpCurUncertainty",&val2);
				if (!err) this->fUpCurUncertainty = val2;
				else this->fUpCurUncertainty = val;
			} 
		////////////////
		err = message->GetParameterAsDouble("CrossCurUncertainty",&val);	// preserve location files with old keyword
		if(!err) { 
				this->fRightCurUncertainty = val;
				this->fLeftCurUncertainty = -val;
			}
		////////////////
		err = message->GetParameterAsDouble("LeftCurUncertainty",&val);
		if(!err) { 
				this->fLeftCurUncertainty = -val;
				err = message->GetParameterAsDouble("RightCurUncertainty",&val2);
				if (!err) this->fRightCurUncertainty = val2;
				else this->fRightCurUncertainty = val;
			}
		////////////////
		model->NewDirtNotification();// tell model about dirt
	}
	
	/////////////////////////////////////////////////
	//  pass on this message to our base class
	/////////////////////////////////////////////////
	return TMover::CheckAndPassOnMessage(message);
}



