#-------------------------------------------------------------------------------
# scope.py
#
# signal scope class
#
# Copyright (C) 2013, Shinya Takamaeda-Yamazaki
# License: Apache 2.0
#-------------------------------------------------------------------------------


import copy
import os
import sys

import pyverilog.vparser.ast as vast

class ScopeName(object):
    def __init__(self, namelist):
        self.namelist = namelist
    def __repr__(self):
        ret = []
        for name in self.namelist:
            ret.append(name)
            ret.append('_')
        return ''.join(ret[:-1])
    def tocode(self):
        return str(self)

class ScopeFrameList(object):
    def __init__(self):
        self.scopeframes = []
        self.scopeframes.append( ScopeFrame(ScopeName(('_',))) )
        self.current = self.scopeframes[0]
        self.globalframe = self.scopeframes[0]
        self.previousframes = {}
        self.previousframes[self.current] = None
        self.nextframes = {}
        self.label_prefix = 's'
        self.label_count = 0
        self.tmp_prefix = 'tmp'
        self.tmp_count = 0
        self.binds = {}

    def getCurrent(self):
        return self.current

    def pushScopeFrame(self, name=None, ftype=None):
        if name is None:
            name = self.label_prefix + str(self.label_count)
            self.label_count += 1
        prefix = copy.deepcopy(self.current.name.namelist)
        framename = ScopeName(prefix + (name,))
        f = ScopeFrame(framename, ftype)
        self.scopeframes.append(f)
        self.previousframes[f] = self.current
        if self.current not in self.nextframes:
            self.nextframes[self.current] = []
        self.nextframes[self.current].append(f)
        self.current = f

    def popScopeFrame(self):
        self.current = self.previousframes[self.current]

    def searchVariable(self, name, store=False):
        if self.current is None: return None
        targ = self.current
        is_global = False
        while targ is not None:
            ret = targ.searchVariable(name)
            if ret: return ret
            if targ.ftype == 'call':
                ret = targ.searchNonlocal(name)
                if ret: continue
                ret = targ.searchGlobal(name)
                if ret: is_global = True
                break
            targ = self.previousframes[targ]
        if not store or is_global:
            ret = self.globalframe.searchVariable(name)
            return ret
        return None

    def addVariable(self, name):
        self.current.addVariable(name)

    def addTmpVariable(self):
        name = self.tmp_prefix + str(self.tmp_count)
        self.tmp_count += 1
        exist = self.searchVariable(name)
        while exist is not None:
            name = self.tmp_prefix + str(self.tmp_count)
            self.tmp_count += 1
            exist = self.searchVariable(name)
        self.current.addVariable(name)
        return self.searchVariable(name)

    def addNonlocal(self, name):
        if self.current is None: return None
        targ = self.current
        while targ is not None:
            if targ.ftype == 'call':
                targ.addNonlocal(name)
                break
            targ = self.previousframes[targ]
        return None

    def addGlobal(self, name):
        if self.current is None: return None
        targ = self.current
        while targ is not None:
            if targ.ftype == 'call':
                targ.addGlobal(name)
                break
            targ = self.previousframes[targ]
        return None

    def searchFunction(self, name, store=False):
        if self.current is None: return None
        targ = self.current
        while targ is not None:
            ret = targ.searchFunction(name)
            if ret: return ret
            targ = self.previousframes[targ]
        ret = self.globalframe.searchFunction(name)
        return ret

    def addFunction(self, func):
        self.current.addFunction(func)
        
    def addBind(self, state, dst, var, cond=None):
        if dst not in self.binds:
            self.binds[dst] = []
        self.binds[dst].append( (state, var, cond) )

    def getBinds(self):
        return self.binds

    #----------------------------------------------------------------------------
    def addBreak(self, count):
        self.current.addBreak(count)

    def addContinue(self, count):
        self.current.addContinue(count)

    def addReturn(self, count, value):
        self.current.addReturn(count, value)

    def setReturnVariable(self, var):
        if self.current is None: return
        targ = self.current
        while targ is not None:
            if targ.ftype == 'call':
                targ.setReturnVariable(var)
                return
            targ = self.previousframes[targ]

    def hasBreak(self):
        return self.current.hasBreak()

    def hasContinue(self):
        return self.current.hasContinue()

    def hasReturn(self):
        return self.current.hasReturn()

    def getUnresolvedBreak(self, p=None):
        ret = []
        ptr = self.current if p is None else p
        ret.extend(ptr.getBreak())
        if ptr not in self.nextframes:
            return tuple(ret)
        for f in self.nextframes[ptr]:
            ret.extend(self.getUnresolvedBreak(f))
        return tuple(ret)

    def getUnresolvedContinue(self, p=None):
        ret = []
        ptr = self.current if p is None else p
        ret.extend(ptr.getContinue())
        if ptr not in self.nextframes:
            return tuple(ret)
        for f in self.nextframes[ptr]:
            ret.extend(self.getUnresolvedContinue(f))
        return tuple(ret)

    def getUnresolvedReturn(self, p=None):
        ret = []
        ptr = self.current if p is None else p
        ret.extend(ptr.getReturn())
        if ptr not in self.nextframes:
            return tuple(ret)
        for f in self.nextframes[ptr]:
            ret.extend(self.getUnresolvedReturn(f))
        return tuple(ret)

    def getReturnVariable(self):
        if self.current is None: return None
        targ = self.current
        while targ is not None:
            if targ.ftype == 'call':
                return targ.getReturnVariable()
            targ = self.previousframes[targ]
        return None

    def clearBreak(self, p=None):
        ptr = self.current if p is None else p
        ptr.clearBreak()
        if ptr not in self.nextframes:
            return
        for f in self.nextframes[ptr]:
            self.clearBreak(f)

    def clearContinue(self, p=None):
        ptr = self.current if p is None else p
        ptr.clearContinue()
        if ptr not in self.nextframes:
            return
        for f in self.nextframes[ptr]:
            self.clearContinue(f)

    def clearReturn(self, p=None):
        ptr = self.current if p is None else p
        ptr.clearReturn()
        if ptr not in self.nextframes:
            return
        for f in self.nextframes[ptr]:
            self.clearReturn(f)

    def clearReturnVariable(self, p=None):
        ptr = self.current if p is None else p
        ptr.clearReturnVariable()
        if ptr not in self.nextframes:
            return
        for f in self.nextframes[ptr]:
            self.clearReturnVariable(f)
        
class ScopeFrame(object):
    def __init__(self, name, ftype=None):
        self.name = name
        self.ftype = ftype
        self.variables = []
        self.nonlocals = []
        self.globals = []
        self.functions = {}

        self.unresolved_break = []
        self.unresolved_continue = []
        self.unresolved_return = []
        self.returnvariable = None

    def addVariable(self, name):
        self.variables.append(name)

    def getVariables(self):
        return tuple(self.variables)

    def addNonlocal(self, name):
        self.nonlocals.append(name)

    def getNonlocals(self):
        return tuple(self.nonlocals)

    def addGlobal(self, name):
        self.globals.append(name)

    def getGlobals(self):
        return tuple(self.globals)

    def addFunction(self, func):
        name = func.name
        self.functions[name] = func

    def getFunctions(self):
        return self.functions
        
    def getName(self):
        return self.name

    def getType(self):
        return self.ftype

    def searchVariable(self, name):
        if name not in self.variables: return None
        return self.name.tocode() + '_' + name

    def searchNonlocal(self, name):
        if name not in self.nonlocals: return None
        return self.name.tocode() + '_' + name

    def searchGlobal(self, name):
        if name not in self.globals: return None
        return self.name.tocode() + '_' + name

    def searchFunction(self, name):
        if name not in self.functions: return None
        return self.functions[name]
    
    def addBreak(self, count):
        self.unresolved_break.append(count)

    def addContinue(self, count):
        self.unresolved_continue.append(count)

    def addReturn(self, count, value):
        self.unresolved_return.append( (count, value) )

    def hasBreak(self):
        if self.unresolved_break: return True
        return False

    def hasContinue(self):
        if self.unresolved_continue: return True
        return False

    def hasReturn(self):
        if self.unresolved_return: return True
        return False

    def getBreak(self):
        return self.unresolved_break

    def getContinue(self):
        return self.unresolved_continue

    def getReturn(self):
        return self.unresolved_return

    def clearBreak(self):
        self.unresolved_break = []

    def clearContinue(self):
        self.unresolved_continue = []

    def clearReturn(self):
        self.unresolved_return = []

    def clearReturnVariable(self):
        self.returnvariable = None

    def setReturnVariable(self, var):
        self.returnvariable = var

    def getReturnVariable(self):
        return self.returnvariable

    def __hash__(self):
        return hash( (self.name, self.ftype, id(self)) )

    def __eq__(self, other):
        if type(self) != type(other): return False
        if self.name != other.name: return False
        if self.ftype != other.ftype: return False
        if id(self) != id(other): return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)
